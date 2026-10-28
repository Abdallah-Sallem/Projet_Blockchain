import copy
import json
import subprocess
import sys
import numpy as np
import pytest
from fedtrace.canonical import model_hash, metadata, digest
from fedtrace.storage import Store
from fedtrace.service import Service
from fedtrace.identity import identity, sign
from fedtrace.ledger import body, Unavailable
from fedtrace.federation import initial, aggregate


@pytest.fixture(scope='module')
def trained(tmp_path_factory):
    s=Service(tmp_path_factory.mktemp('trained'))
    s.run(rounds=2,epochs=2,poison=True,experiment='test')
    return s


def test_canonical_process_order_roundtrip(tmp_path):
    a={'weight':np.array([1,2],dtype='float32'),'bias':np.array([3],dtype='float32')}
    assert model_hash(a)==model_hash(dict(reversed(list(a.items()))))
    assert model_hash(a)!=model_hash(a,'update')
    store=Store(tmp_path)
    store.save_model('a.npz',a)
    assert model_hash(a)==model_hash(store.load_model('a.npz'))
    code="import numpy as np;from fedtrace.canonical import model_hash;print(model_hash({'weight':np.array([1,2],dtype='float32'),'bias':np.array([3],dtype='float32')}))"
    assert subprocess.check_output([sys.executable,'-c',code],text=True).strip()==model_hash(a)
    assert model_hash({'x':np.array([1,2],dtype='>f4')})==model_hash({'x':np.array([1,2],dtype='<f4')})


@pytest.mark.parametrize('change',['value','shape','name','dtype'])
def test_canonical_sensitive(change):
    a={'x':np.array([1,2],dtype='float32')}
    b=copy.deepcopy(a)
    if change=='value':b['x'][0]=3
    if change=='shape':b['x']=b['x'].reshape(1,2)
    if change=='name':b={'y':b['x']}
    if change=='dtype':b['x']=b['x'].astype('float64')
    assert model_hash(a)!=model_hash(b)


@pytest.mark.parametrize('x',[np.array([np.nan]),np.array([np.inf]),np.array(['x']),np.array([object()])])
def test_invalid_tensors(x):
    with pytest.raises(ValueError):model_hash({'x':x})


def test_metadata():
    assert metadata({'b':2,'a':1})==metadata({'a':1,'b':2})
    with pytest.raises(ValueError):metadata({'x':float('nan')})


def test_scalar_shape_and_invalid_names():
    assert model_hash({'x':np.array(1,dtype='float32')})!=model_hash({'x':np.array([1],dtype='float32')})
    for bad in [[],{}, {'':np.array([1])}, {1:np.array([1]),'x':np.array([1])}]:
        with pytest.raises(ValueError):model_hash(bad)


def test_nominal_provenance_and_processes(trained):
    s=trained
    d=s.infer([.4,-.3,.8,.2,-.1,.5])
    assert d['state']=='confirmed' and s.verify(d['id'])['valid']
    tree=s.ledger.provenance(d['id'])
    assert tree['children'][0]['record']['body']['round']==2
    assert tree['children'][0]['children'][0]['children'][0]['record']['body']['round']==0
    workers=s.store.get('test:r1:workers')
    assert len({w['pid'] for w in workers})==3
    assert len(s.ledger.history('test:model'))==3
    records=s.ledger.records()
    for model in [r for r in records if r['body']['kind']=='model' and r['body']['round']]:
        assert all(s.ledger.get(r)['receipt']['sequence']<model['receipt']['sequence'] for r in model['body']['accepted']+list(model['body']['rejected']))


def test_explanation_tamper(trained):
    d=trained.infer([0]*6)
    p=trained.store.path(d['path'])
    p.write_bytes(p.read_bytes()+b' ')
    assert trained.verify(d['id'])['state']=='tampered'


def test_uncertified_and_outage_gate(trained):
    s=trained
    deployed=s.store.get('deployed')
    with pytest.raises(Unavailable):
        (s.store.home/'ledger.offline').touch()
        try:s.infer([0]*6)
        finally:(s.store.home/'ledger.offline').unlink()
    weights=s.store.load_model(deployed['path']);weights['bias']+=10
    s.store.save_model('substituted.npz',weights)
    s.store.put('deployed',{**deployed,'path':'substituted.npz'})
    try:
        with pytest.raises(ValueError,match='uncertified'):s.infer([0]*6)
    finally:s.store.put('deployed',deployed)


def test_poison_same_updates(trained):
    s=trained
    workers=s.store.get('test:r1:workers')
    updates=[s.store.load_model(w['artifact']) for w in workers]
    counts=[w['envelope']['body']['samples'] for w in workers]
    _,a,rejected=aggregate(updates,counts,'robust')
    _,b,r=aggregate(updates,counts,'fedavg')
    assert 2 not in a and 2 in rejected and b==[0,1,2] and not r
    assert len(s.ledger.get('test:r1:model')['body']['rejected'])==1


def test_unauthorized_duplicates_and_invalid_references(trained):
    s=trained
    original=s.ledger.get('test:r1:clinic-1')
    envelope={k:original[k] for k in ('body','author','signature')}
    assert s.ledger.anchor(envelope)==original['receipt']
    altered=copy.deepcopy(envelope);altered['body']['samples']+=1
    with pytest.raises(ValueError,match='conflicting'):s.ledger.anchor(altered)
    b=copy.deepcopy(envelope['body']);b['id']='unauthorized'
    bad=sign(b,identity(s.store.home,'attacker'))
    with pytest.raises(ValueError,match='unauthorized'):s.ledger.anchor(bad)
    b=copy.deepcopy(s.ledger.get('test:r1:model')['body']);b['id']='bad-reference';b['accepted']=['missing']
    with pytest.raises(ValueError,match='reference'):s.ledger.anchor(sign(b,identity(s.store.home,'server')))
    b['accepted']=['test:r2:clinic-1']
    with pytest.raises(ValueError,match='reference'):s.ledger.anchor(sign(b,identity(s.store.home,'server')))


def test_outbox_crash_lost_response(tmp_path):
    s=Service(tmp_path)
    s.configure(rounds=1,epochs=1,experiment='crash')
    row=s.outbox.rows()[0]
    envelope=json.loads(row['envelope'])
    s.ledger.anchor(envelope) # commit succeeded, process died before response persisted
    with s.store.db:s.store.db.execute("UPDATE outbox SET state='submitted'")
    restarted=Service(tmp_path)
    restarted.outbox.flush(force=True)
    assert restarted.outbox.confirmed(envelope['body']['id'])
    assert len(restarted.ledger.records())==1


def test_outbox_durable_outage(tmp_path,monkeypatch):
    # A fixed clock tests backoff policy independently of slow Windows key/DB I/O.
    monkeypatch.setattr('fedtrace.outbox.time.time',lambda:1000.0)
    s=Service(tmp_path);s.configure(rounds=1,epochs=1,experiment='outage')
    (tmp_path/'ledger.offline').touch()
    s.advance()
    assert s.outbox.rows()[0]['state']=='pending' and not s.store.get('deployed')
    restarted=Service(tmp_path)
    restarted.advance()
    assert restarted.outbox.rows()[0]['attempts']==1 # backoff honored
    (tmp_path/'ledger.offline').unlink()
    job=restarted.advance(force=True)
    assert job['state']=='complete'
    count=len(restarted.ledger.records());restarted.advance(force=True)
    assert len(restarted.ledger.records())==count==5


def test_pending_decision_after_successful_inference(trained,monkeypatch):
    original=trained.ledger.anchor
    def fail_decision(e):
        if e['body']['kind']=='decision':raise Unavailable('outage_after_inference')
        return original(e)
    monkeypatch.setattr(trained.ledger,'anchor',fail_decision)
    d=trained.infer([0]*6)
    assert d['state']=='pending' and trained.store.get('decision:'+d['id'])
    monkeypatch.setattr(trained.ledger,'anchor',original)
    trained.outbox.flush(force=True)
    assert trained.verify(d['id'])['valid']


def test_exact_explanation_bytes_delivered(trained):
    d=trained.infer([0]*6)
    assert digest(d['explanation_artifact'].encode())==d['explanation_hash']
    assert d['explanation_artifact'].encode()==trained.store.path(d['path']).read_bytes()


def test_recover_decision_before_enqueue(trained):
    d=trained.infer([0]*6)
    with trained.store.db:
        trained.store.db.execute('DELETE FROM outbox WHERE id=?',(d['id'],))
    restarted=Service(trained.store.home)
    restarted.advance(force=True)
    assert restarted.outbox.confirmed(d['id'])


def test_recover_model_staged_before_enqueue(tmp_path,monkeypatch):
    s=Service(tmp_path);s.configure(rounds=1,epochs=1,experiment='modelcrash')
    enqueue=s.outbox.enqueue
    def crash(envelope,dependencies=()):
        if envelope['body']['kind']=='model' and envelope['body']['round']==1:
            raise RuntimeError('crash_before_enqueue')
        return enqueue(envelope,dependencies)
    monkeypatch.setattr(s.outbox,'enqueue',crash)
    with pytest.raises(RuntimeError,match='crash_before_enqueue'):s.advance(force=True)
    staged=s.store.get('job')['model_envelope']
    restarted=Service(tmp_path);assert restarted.advance(force=True)['state']=='complete'
    anchored=restarted.ledger.get(staged['body']['id'])
    assert {k:anchored[k] for k in ('body','author','signature')}==staged


def test_chain_tamper_fails_closed(tmp_path):
    s=Service(tmp_path);s.configure(rounds=1,experiment='integrity');s.outbox.flush()
    with s.ledger.db:s.ledger.db.execute("UPDATE records SET previous=?",('1'*64,))
    with pytest.raises(Unavailable,match='integrity'):s.ledger.records()


def test_api_auth_and_demo_guards(tmp_path,monkeypatch):
    from fedtrace import api
    from fastapi.testclient import TestClient
    monkeypatch.setattr(api,'HOME',str(tmp_path))
    monkeypatch.setattr(api,'DEMO',False)
    client=TestClient(api.app)
    assert client.get('/api/status').status_code==200
    assert client.post('/api/experiments',json={}).status_code==401
    token=Service(tmp_path).store.get('api_token')
    headers={'Authorization':'Bearer '+token}
    assert client.post('/api/demo/ledger/offline',json={},headers=headers).status_code==403
    assert client.post('/api/diagnose',json={'features':[0]*6},headers=headers).json()['detail']['reason']=='uncertified_model'
    assert client.post('/api/diagnose',json={'features':[0]*6,'clinic':'clinic-2'},headers=headers).status_code==422
