"""Repeatable A-E demonstrations. All expected outcomes are asserted."""
import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from fedtrace.service import Service
from fedtrace.federation import launch_clinics, aggregate, evaluate
from fedtrace.canonical import model_hash
from fedtrace.ledger import Unavailable, body
from fedtrace.identity import sign,identity


def run(root,scenario='all'):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    results={}
    s=Service(root/'workflow')
    s.run(rounds=2,epochs=3,poison=True,experiment='scenario'+uuid.uuid4().hex)
    exp=s.store.get('job')['config']['experiment']
    if scenario in ('all','A'):
        d=s.infer([.4,-.3,.8,.2,-.1,.5]);assert s.verify(d['id'])['valid']
        tree=s.ledger.provenance(d['id'])
        results['A']={'decision':d['id'],'verified':True,'provenance':tree}
    if scenario in ('all','B'):
        d=s.infer([0]*6);p=s.store.path(d['path']);p.write_bytes(p.read_bytes()+b' ')
        assert s.verify(d['id'])['state']=='tampered'
        results['B']=s.verify(d['id'])
    if scenario in ('all','C'):
        deployed=s.store.get('deployed');w=s.store.load_model(deployed['path']);w['bias']+=7
        s.store.save_model('unanchored.npz',w);s.store.put('deployed',{**deployed,'path':'unanchored.npz'})
        try:
            s.infer([0]*6)
            raise AssertionError('uncertified model accepted')
        except ValueError as e:assert str(e)=='uncertified_model'
        finally:s.store.put('deployed',deployed)
        results['C']={'refused':True,'reason':'uncertified_model'}
    if scenario in ('all','D'):
        workers=s.store.get(exp+':r1:workers');updates=[s.store.load_model(w['artifact']) for w in workers]
        counts=[w['envelope']['body']['samples'] for w in workers]
        robust,good,rejected=aggregate(updates,counts,'robust');avg,all_,_=aggregate(updates,counts,'fedavg')
        assert 2 in rejected and all_==[0,1,2]
        # A second model event on the same logical key replays EXACT anchored updates and parent.
        original=s.ledger.get(exp+':r1:model')['body']
        replay_weights={k:s.store.load_model(exp+'/root.npz')[k]+avg[k] for k in avg}
        s.store.save_model(exp+'/r1/fedavg-replay.npz',replay_weights)
        replay=body('model',exp+':r1:fedavg-replay','server',exp,1,key=exp+':model',hash=model_hash(replay_weights),
                    parent=original['parent'],accepted=[w['envelope']['body']['id'] for w in workers],rejected={},strategy='fedavg',configuration={'replay_of':original['id'],'same_updates':True},
                    metrics={'test':evaluate(replay_weights,42+900001)})
        s.outbox.enqueue(sign(replay,identity(s.store.home,'server')),[w['envelope']['body']['id'] for w in workers]);s.outbox.flush(force=True)
        assert s.outbox.confirmed(replay['id'])
        results['D']={'same_update_hashes':[model_hash(u,'update') for u in updates], 'robust_rejected':rejected,'fedavg_accepted':all_, 'robust_model':original['id'],'fedavg_model':replay['id']}
    if scenario in ('all','E'):
        home=root/'outage';o=Service(home);exp='outage'+uuid.uuid4().hex
        job=o.configure(rounds=1,epochs=2,experiment=exp);o.outbox.flush(force=True)
        workers=launch_clinics(home,job['config'],1,job['parent'],job['parent_path'])
        o.store.put(exp+':r1:workers',workers)
        (home/'ledger.offline').touch();o.advance(force=True)
        assert o.store.get('job')['phase']=='contributions' and not o.store.get('deployed')
        pending_before=[r['id'] for r in o.outbox.rows() if r['state']=='pending'];assert len(pending_before)==3
        # A real new interpreter reopens durable state while the ledger is still offline.
        subprocess.run([sys.executable,'-m','fedtrace.cli','resume','--home',str(home)],check=True,capture_output=True)
        (home/'ledger.offline').unlink();o=Service(home);o.advance(force=True)
        assert o.store.get('job')['state']=='complete'
        d=o.infer([0]*6);assert o.verify(d['id'])['valid']
        count=len(o.ledger.records());o.outbox.flush(force=True);assert len(o.ledger.records())==count==6
        results['E']={'pending_survived_restart':pending_before,'records_after_replay':count,'no_duplicates':True,'provenance':o.ledger.provenance(d['id'])}
    return results


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',choices=['all','A','B','C','D','E'],default='all');parser.add_argument('--home',default='runtime/scenarios/'+uuid.uuid4().hex)
    args=parser.parse_args();results=run(args.home,args.scenario)
    path=Path('reports/scenarios.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Verified scenarios: '+', '.join(results)+'; evidence: '+str(path))


if __name__=='__main__':main()
