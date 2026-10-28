import json
import os
import secrets
import uuid
from .canonical import model_hash, metadata, digest
from .identity import identity, sign
from .storage import Store
from .ledger import LocalLedger, Unavailable, body
from .outbox import Outbox
from .federation import initial, launch_clinics, aggregate, evaluate, FEATURES
import numpy as np


class Service:
    def __init__(self, home='runtime/demo', ledger=None):
        self.store = Store(home)
        ids = self.store.get('identities', {})
        if not ids:
            ids = {name: identity(home, name).address for name in ['server']+['clinic-%d'%i for i in range(1, 4)]}
            self.store.put('identities', ids)
        self.ledger = ledger or LocalLedger(home, ids)
        self.outbox = Outbox(self.store, self.ledger)
        if not self.store.get('api_token'):
            self.store.put('api_token', secrets.token_urlsafe(32))

    def configure(self, clinics=3, rounds=3, epochs=6, seed=42, strategy='robust', poison=False,
                  dimensions=6, non_iid=True, experiment=None):
        if not 3 <= clinics <= 12 or not 1 <= rounds <= 100 or not 1 <= epochs <= 1000 or not 1 <= dimensions <= 100000:
            raise ValueError('invalid_configuration')
        if strategy not in ('robust', 'fedavg'):
            raise ValueError('invalid_strategy')
        if self.store.get('job', {}).get('state') not in (None, 'complete'):
            raise ValueError('experiment_in_progress')
        experiment = experiment or uuid.uuid4().hex
        if not experiment.isalnum() or self.store.get('experiment:'+experiment):
            raise ValueError('invalid_or_duplicate_experiment')
        c = dict(clinics=clinics, rounds=rounds, epochs=epochs, seed=seed, strategy=strategy,
                 poison=poison, dimensions=dimensions, non_iid=non_iid, experiment=experiment, lr=.15, threshold=3.)
        ids = self.store.get('identities')
        for i in range(1,clinics+1):
            name = 'clinic-%d'%i
            ids[name] = identity(self.store.home, name).address
        self.store.put('identities',ids)
        self.ledger.identities = ids
        path = self.store.save_model(experiment+'/root.npz', initial(dimensions))
        root_id = experiment+':r0:model'
        root = body('model', root_id, 'server', experiment, 0, key=experiment+':model',
                    hash=model_hash(initial(dimensions)), parent=None, accepted=[], rejected={},
                    strategy='initial', configuration={}, metrics={})
        root_envelope = sign(root, identity(self.store.home,'server'))
        job = dict(config=c, round=1, parent=root_id, parent_path=path, phase='root', state='running',root_envelope=root_envelope)
        self.store.put('job',job)
        self.store.put('experiment:'+experiment,c)
        self.outbox.enqueue(root_envelope)
        return job

    def advance(self, force=False):
        # Recover a crash between saving a generated decision and enqueueing its anchor.
        for row in self.store.db.execute("SELECT value FROM objects WHERE key LIKE 'decision:%'").fetchall():
            decision = json.loads(row[0])
            if 'envelope' in decision:
                self.outbox.enqueue(decision['envelope'],[decision['model']])
        job = self.store.get('job')
        if job and job['phase'] == 'root':
            self.outbox.enqueue(job['root_envelope'])
        self.outbox.flush(force)
        if not job or job['state'] == 'complete':
            return job
        c, r = job['config'], job['round']
        if job['phase'] == 'root':
            if not self.outbox.confirmed(job['parent']):
                return job
            job['phase'] = 'train'
            self.store.put('job',job)
        if job['phase'] == 'train':
            result_key = '%s:r%d:workers'%(c['experiment'],r)
            workers = self.store.get(result_key)
            if workers is None:
                workers = launch_clinics(self.store.home,c,r,job['parent'],job['parent_path'])
                self.store.put(result_key,workers)
            for w in workers:
                self.outbox.enqueue(w['envelope'],[job['parent']])
            job.update(phase='contributions',workers=workers)
            self.store.put('job',job)
            self.outbox.flush(force)
        if job['phase'] == 'contributions':
            workers = job['workers']
            if not all(self.outbox.confirmed(w['envelope']['body']['id']) for w in workers):
                return job
            # Require live confirmation, even if outbox has cached confirmed receipts.
            for w in workers:
                if not self.ledger.get(w['envelope']['body']['id']):
                    raise Unavailable('missing_live_contribution')
            updates = [self.store.load_model(w['artifact']) for w in workers]
            if any(model_hash(u,'update') != w['envelope']['body']['hash'] for u,w in zip(updates,workers)):
                raise ValueError('update_integrity_failure')
            delta, accepted, rejected = aggregate(updates,[w['envelope']['body']['samples'] for w in workers],c['strategy'],c['threshold'])
            parent = self.store.load_model(job['parent_path'])
            weights = {k:parent[k]+delta[k] for k in parent}
            path = self.store.save_model('%s/r%d/global.npz'%(c['experiment'],r),weights)
            rid = '%s:r%d:model'%(c['experiment'],r)
            model_body = body('model',rid,'server',c['experiment'],r,key=c['experiment']+':model',hash=model_hash(weights),parent=job['parent'],
                              accepted=[workers[i]['envelope']['body']['id'] for i in accepted],
                              rejected={workers[i]['envelope']['body']['id']:reason for i,reason in rejected.items()},
                              strategy=c['strategy'],configuration={'threshold':c['threshold'],'weighting':'declared_training_samples'},
                              metrics={'validation':evaluate(weights,c['seed']+900000), 'test':evaluate(weights,c['seed']+900001)})
            # Stage the EXACT signed envelope before enqueueing, so restart cannot
            # regenerate a timestamp/signature under an already submitted stable ID.
            job.update(phase='model',model=rid,model_path=path,model_envelope=sign(model_body,identity(self.store.home,'server')),
                       model_dependencies=[w['envelope']['body']['id'] for w in workers])
            self.store.put('job',job)
        if job['phase'] == 'model':
            self.outbox.enqueue(job['model_envelope'],job['model_dependencies'])
            self.outbox.flush(force)
            if not self.outbox.confirmed(job['model']):
                return job
            record = self.ledger.get(job['model'])
            if not record:
                raise Unavailable('missing_live_model')
            self.store.put('deployed',dict(path=job['model_path'],record=job['model'],hash=record['body']['hash']))
            if r >= c['rounds']:
                job['state'] = 'complete'
            else:
                job.update(round=r+1,parent=job['model'],parent_path=job['model_path'],phase='train')
                job.pop('workers',None)
            self.store.put('job',job)
        return job

    def run(self, **config):
        self.configure(**config)
        while True:
            job = self.advance(force=True)
            if job['state'] == 'complete':
                return job
            if job['phase'] in ('root','contributions','model'):
                raise Unavailable('round_paused_pending_anchors')

    def infer(self, features, clinic='clinic-1'):
        if clinic not in self.store.get('identities') or not clinic.startswith('clinic-'):
            raise ValueError('unauthorized_clinic')
        deployed = self.store.get('deployed')
        if not deployed:
            raise ValueError('uncertified_model')
        # Snapshot arrays are private to this call. No shared mutable deployment pointer afterward.
        weights = self.store.load_model(deployed['path'])
        h = model_hash(weights)
        record = self.ledger.get(deployed['record'])
        if not record or record['body']['kind'] != 'model' or record['body']['hash'] != h:
            raise ValueError('uncertified_model')
        for a in weights.values():
            a.setflags(write=False)
        x = np.asarray(features,dtype='float32')
        if x.shape != weights['weight'].shape or not np.isfinite(x).all() or np.abs(x).max()>10:
            raise ValueError('invalid_synthetic_features')
        contributions = x*weights['weight']
        logit = float(contributions.sum()+weights['bias'][0])
        p = float(1/(1+np.exp(-np.clip(logit,-40,40))))
        case, decision = uuid.uuid4().hex, uuid.uuid4().hex
        explanation = dict(schema=1,method='linear_logit_contributions',model_hash=h,
                           intercept=float(weights['bias'][0]), logit=logit,
                           features=[{'name':FEATURES[i] if i<len(FEATURES) else 'synthetique_%d'%i,'value':float(v)} for i,v in enumerate(contributions)],
                           notice='Simulation pédagogique sans validation clinique')
        exact = metadata(explanation)
        path = self.store.write_bytes('decisions/'+decision+'/explanation.json',exact)
        self.store.write_bytes('decisions/'+decision+'/case.json',metadata({'pseudonym':case,'features':x.tolist()}))
        b = body('decision',decision,clinic,record['body']['experiment'],record['body']['round'],key='case:'+case,
                 model=record['body']['id'],hash=h,explanation_hash=digest(exact),case=case,probability=p,validation='educational_simulation')
        envelope = sign(b,identity(self.store.home,clinic))
        pending = dict(id=decision,path=path,model=record['body']['id'],hash=h,probability=p)
        self.store.put('decision:'+decision,{**pending,'envelope':envelope})
        # Save exact signed envelope durably before any ledger submission.
        self.outbox.enqueue(envelope,[record['body']['id']])
        self.outbox.flush()
        return {**pending, 'state':'confirmed' if self.outbox.confirmed(decision) else 'pending',
                'explanation':explanation,'explanation_artifact':exact.decode('utf-8'),
                'explanation_hash':digest(exact)}

    def verify(self, decision):
        d = self.store.get('decision:'+decision)
        if not d:
            raise KeyError(decision)
        record = self.ledger.get(decision)
        if not record:
            return {'state':'pending','valid':False}
        exact = self.store.path(d['path']).read_bytes()
        valid = self.ledger.verify_decision(decision,d['hash'],exact)
        return {'state':'confirmed' if valid else 'tampered','valid':valid,'actual_hash':digest(exact),
                'anchored_hash':record['body']['explanation_hash']}

    def status(self):
        try:
            records = self.ledger.records()
            availability = 'available'
        except Unavailable:
            records,availability = [],'unavailable'
        deployed = self.store.get('deployed')
        certification = 'unavailable' if availability == 'unavailable' else 'uncertified'
        if deployed and availability == 'available':
            try:
                actual = model_hash(self.store.load_model(deployed['path']))
                if any(r['body']['id']==deployed['record'] and r['body']['kind']=='model' and r['body']['hash']==actual for r in records):
                    certification = 'confirmed'
            except (ValueError,OSError,KeyError):
                certification = 'uncertified'
        return {'ledger':availability,'adapter':self.ledger.label,'job':self.store.get('job'),
                'deployed':deployed,'certification':certification,'identities':self.store.get('identities'),
                'records':records,'outbox':[{k:v for k,v in r.items() if k not in ('envelope','dependencies')} for r in self.outbox.rows()],
                'notice':'Données synthétiques • Simulation pédagogique sans validation clinique'}
