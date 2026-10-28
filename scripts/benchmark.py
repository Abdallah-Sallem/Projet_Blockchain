"""Paired measurements: train once per seed/size, replay identical updates in all modes."""
import argparse
import csv
import json
import statistics
import time
import uuid
from pathlib import Path
from fedtrace.service import Service
from fedtrace.federation import launch_clinics, aggregate, evaluate
from fedtrace.canonical import metadata,model_hash
from fedtrace.identity import sign,identity
from fedtrace.ledger import body,Unavailable


def size(s):
    s.ledger.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return sum(p.stat().st_size for p in s.store.home.glob('ledger.sqlite*'))


def measure(home,dimensions,seed):
    s=Service(home)
    exp='bench'+uuid.uuid4().hex
    job=s.configure(rounds=1,epochs=2,seed=seed,dimensions=dimensions,non_iid=True,experiment=exp)
    s.outbox.flush(force=True)
    start=time.perf_counter()
    workers=launch_clinics(home,job['config'],1,job['parent'],job['parent_path'])
    training=time.perf_counter()-start
    updates=[s.store.load_model(w['artifact']) for w in workers]
    counts=[w['envelope']['body']['samples'] for w in workers]
    rows=[]
    for mode in ['federation_only','global_only','full_certification']:
        before=size(s);start=time.perf_counter()
        anchor_start=time.perf_counter()
        if mode=='full_certification':
            for w in workers:s.outbox.enqueue(w['envelope'],[job['parent']])
            s.outbox.flush(force=True)
            assert all(s.outbox.confirmed(w['envelope']['body']['id']) for w in workers)
        contribution_time=time.perf_counter()-anchor_start
        delta,accepted,rejected=aggregate(updates,counts,'robust')
        weights={k:s.store.load_model(job['parent_path'])[k]+delta[k] for k in delta}
        metrics=evaluate(weights,seed+900001)
        anchor_time=contribution_time;written=[];record_id=None
        if mode!='federation_only':
            anchor_start=time.perf_counter()
            record_id=exp+':'+mode
            # Ablation: standalone checkpoint, no contribution lineage and no inference gate.
            # Full mode is the production round schema and validates all contribution references.
            b=body('model',record_id,'server',exp,1 if mode=='full_certification' else 0,key=exp+':model',
                   hash=model_hash(weights),parent=job['parent'] if mode=='full_certification' else None,
                   accepted=[workers[i]['envelope']['body']['id'] for i in accepted] if mode=='full_certification' else [],
                   rejected={workers[i]['envelope']['body']['id']:v for i,v in rejected.items()} if mode=='full_certification' else {},
                   strategy='robust',configuration={'threshold':3.,'mode':mode},metrics=metrics)
            envelope=sign(b,identity(home,'server'))
            deps=[w['envelope']['body']['id'] for w in workers] if mode=='full_certification' else []
            s.outbox.enqueue(envelope,deps);s.outbox.flush(force=True);assert s.outbox.confirmed(record_id)
            anchor_time+=time.perf_counter()-anchor_start
            written=([w['envelope'] for w in workers] if mode=='full_certification' else [])+[envelope]
        total=training+time.perf_counter()-start
        after=size(s)
        provenance=None
        if record_id:
            t=time.perf_counter();s.ledger.provenance(record_id);provenance=time.perf_counter()-t
        rows.append(dict(mode=mode,dimensions=dimensions,seed=seed,clinics=3,epochs=2,training_seconds=training,
                         round_seconds=total,anchoring_seconds=anchor_time,transactions=len(written),
                         payload_bytes=sum(len(metadata(w)) for w in written),storage_growth_bytes=after-before,
                         provenance_seconds=provenance,accuracy=metrics['accuracy']))
    s.store.save_model('benchmark-global.npz',weights)
    s.store.put('deployed',{'path':'benchmark-global.npz','record':record_id,'hash':model_hash(weights)})
    refusals=0
    for _ in range(5):
        try:d=s.infer([0]*dimensions)
        except (ValueError,Unavailable):refusals+=1
    assert refusals==0
    detected=0
    for _ in range(5):
        p=s.store.path(d['path']);original=p.read_bytes();p.write_bytes(original+b' ')
        detected+=s.verify(d['id'])['state']=='tampered';p.write_bytes(original)
    (s.store.home/'ledger.offline').touch()
    unavailable=0
    try:s.infer([0]*dimensions)
    except Unavailable:unavailable=1
    finally:(s.store.home/'ledger.offline').unlink()
    for row in rows:
        row.update(tampering_trials=5 if row['mode']=='full_certification' else None,tampering_detected=detected if row['mode']=='full_certification' else None,
                   healthy_gate_trials=5 if row['mode']=='full_certification' else None,false_refusals=refusals if row['mode']=='full_certification' else None,
                   availability_refusals=unavailable if row['mode']=='full_certification' else None)
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--dimensions',nargs='+',type=int,default=[6,600]);args=parser.parse_args()
    output=Path('benchmarks');output.mkdir(exist_ok=True)
    rows=[]
    for dims in args.dimensions:
        for repeat in range(args.repeats):
            print('Measuring dimensions=%d repeat=%d'%(dims,repeat+1),flush=True)
            rows+=measure(Path('runtime/benchmarks')/uuid.uuid4().hex,dims,42+repeat)
            (output/'raw.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    with (output/'raw.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[]
    for dims in args.dimensions:
        for mode in ['federation_only','global_only','full_certification']:
            group=[r for r in rows if r['dimensions']==dims and r['mode']==mode]
            times=[r['round_seconds'] for r in group]
            summary.append(dict(mode=mode,dimensions=dims,n=len(group),mean_seconds=statistics.mean(times),
                                std_seconds=statistics.stdev(times) if len(times)>1 else 0,
                                transactions_per_round=group[0]['transactions'],mean_anchoring_seconds=statistics.mean(r['anchoring_seconds'] for r in group),
                                mean_payload_bytes=statistics.mean(r['payload_bytes'] for r in group),mean_storage_growth_bytes=statistics.mean(r['storage_growth_bytes'] for r in group)))
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    colors=['#97b7aa','#4a8d71','#175c46']
    for idx,mode in enumerate(['federation_only','global_only','full_certification']):
        group=[r for r in summary if r['mode']==mode]
        x=[i+(idx-1)*.23 for i in range(len(group))]
        axes[0].bar(x,[r['mean_seconds'] for r in group],width=.23,yerr=[r['std_seconds'] for r in group],label=mode,color=colors[idx],capsize=3)
        axes[1].bar(x,[r['mean_payload_bytes'] for r in group],width=.23,label=mode,color=colors[idx])
    for ax in axes:
        ax.set_xticks(range(len(args.dimensions)),[str(d) for d in args.dimensions]);ax.set_xlabel('Nombre de paramètres de poids (+ biais)');ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('Durée du round (s), moyenne ± écart-type');axes[1].set_ylabel('Octets JSON signés par round')
    axes[0].legend(fontsize=7);fig.tight_layout();fig.savefig(output/'comparison.png',dpi=180);fig.savefig(output/'comparison.svg')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
