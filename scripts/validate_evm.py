"""Run against the deployed local RPC chain; never substitutes a mock provider."""
import json
import uuid
from pathlib import Path
from fedtrace.service import Service
from fedtrace.evm import EvmLedger


def main():
    home=Path('runtime/evm-validation')/uuid.uuid4().hex
    s=Service(home)
    s.ledger=EvmLedger.from_env(s.store.get('identities'))
    s.outbox.ledger=s.ledger
    s.run(rounds=2,epochs=3,experiment='evm'+uuid.uuid4().hex)
    d=s.infer([.4,-.3,.8,.2,-.1,.5]);assert d['state']=='confirmed'
    assert s.verify(d['id'])['valid']
    record=s.ledger.get(d['id'])
    assert s.ledger.contract.functions.verifyDecision(s.ledger.key(d['id']),bytes.fromhex(d['hash']),bytes.fromhex(d['explanation_hash'])).call()
    assert len(s.ledger.history(record['body']['experiment']+':model'))==3
    tree=s.ledger.provenance(d['id']);assert tree['children'][0]['children'][0]['children'][0]['record']['body']['round']==0
    records=[r for r in s.ledger.records() if r['body']['experiment']==record['body']['experiment']]
    summary={'adapter':'evm-dev-chain','chain_id':s.ledger.w3.eth.chain_id,'contract':s.ledger.contract.address,
             'record_count':len(records),'verified_decision':d['id'],'complete_model_history':3,'contract_verify_decision':True,
             'receipts':[dict(record=r['body']['id'],kind=r['body']['kind'],**r['receipt'],
                              gas_used=s.ledger.w3.eth.get_transaction_receipt(r['receipt']['id']).gasUsed) for r in records]}
    Path('reports').mkdir(exist_ok=True)
    Path('reports/evm-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('Real EVM workflow verified: %d records; provenance to root; native contract decision verification.'%len(records))


if __name__=='__main__':main()
