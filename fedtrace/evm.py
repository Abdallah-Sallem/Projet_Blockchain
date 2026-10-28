"""Real RPC EVM adapter. Metadata semantics share the Python validator.

The contract authenticates signatures and dependencies. The gateway is trusted
to bind structured fields to canonical JSON. This is not a distributed deployment.
"""
import json
import os
from pathlib import Path
from web3 import Web3
from web3.exceptions import Web3Exception
from .canonical import metadata, digest
from .ledger import LedgerQueries, Unavailable, validate


class EvmLedger(LedgerQueries):
    label = 'EVM · nœud de développement (transactions réelles)'

    def __init__(self,rpc,address,key,identities):
        self.w3=Web3(Web3.HTTPProvider(rpc,request_kwargs={'timeout':10}))
        self.account=self.w3.eth.account.from_key(key)
        abi=json.loads(Path('contracts/artifacts/FedTrace.json').read_text())['abi']
        self.contract=self.w3.eth.contract(address=Web3.to_checksum_address(address),abi=abi)
        self.identities=identities

    @classmethod
    def from_env(cls,identities):
        path=Path(os.getenv('FEDTRACE_EVM_DEPLOYMENT','runtime/evm/deployment.json'))
        config=json.loads(path.read_text()) if path.exists() else {}
        return cls(os.getenv('FEDTRACE_RPC',config.get('rpc','http://127.0.0.1:8545')),
                   os.getenv('FEDTRACE_CONTRACT') or config['address'],
                   os.getenv('FEDTRACE_EVM_KEY') or config['key'],identities)

    def check(self):
        if not self.w3.is_connected():
            raise Unavailable('ledger_unavailable')
        if not self.w3.eth.get_code(self.contract.address):
            raise Unavailable('contract_unavailable')

    def transact(self,function):
        try:
            self.check()
            tx=function.build_transaction({'from':self.account.address,'nonce':self.w3.eth.get_transaction_count(self.account.address,'pending'),'chainId':self.w3.eth.chain_id})
            signed=self.account.sign_transaction(tx)
            txid=self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt=self.w3.eth.wait_for_transaction_receipt(txid,timeout=30)
            if receipt.status != 1:
                raise ValueError('contract_reverted')
            return receipt
        except (Web3Exception,OSError) as exc:
            raise Unavailable('evm_submission_or_confirmation_unavailable') from exc

    @staticmethod
    def key(value):
        return bytes.fromhex(digest(value.encode())) if value else bytes(32)

    def get(self,record_id):
        try:
            self.check()
            item=self.contract.functions.get(self.key(record_id)).call()
            if not item[4]:
                return None
            events=self.contract.events.Anchored().get_logs(from_block=0,to_block='latest',argument_filters={'id':self.key(record_id)})
            if not events:
                raise Unavailable('confirmation_missing')
            event=events[0]
            return {'body':json.loads(bytes(item[1]).decode()),'signature':bytes(item[2]).hex(),'author':item[3],
                    'receipt':{'id':event['transactionHash'].hex(),'block':event['blockNumber'],'confirmed':True,'adapter':'evm-dev-chain'}}
        except (Web3Exception,OSError) as exc:
            raise Unavailable('ledger_unavailable') from exc

    def records(self):
        try:
            self.check()
            ids=[self.contract.functions.ids(i).call() for i in range(self.contract.functions.count().call())]
            result=[]
            for id_ in ids:
                item=self.contract.functions.get(id_).call()
                result.append(self.get(json.loads(bytes(item[1]).decode())['id']))
            return result
        except (Web3Exception,OSError) as exc:
            raise Unavailable('ledger_unavailable') from exc

    def anchor(self,envelope):
        self.check()
        b=envelope['body']
        old=self.get(b['id'])
        if old:
            if {k:old[k] for k in ('body','signature','author')} != envelope:
                raise ValueError('conflicting_duplicate')
            return old['receipt']
        validate(envelope,self.identities,self.get)
        # Only the gateway can enroll demo identities, from the trusted local roster.
        author=Web3.to_checksum_address(envelope['author'])
        role=2 if b['actor']=='server' else 1
        if self.contract.functions.roles(author).call()!=role:
            self.transact(self.contract.functions.setWriter(author,role))
        refs=(b['accepted']+list(b['rejected'])) if b['kind']=='model' else []
        parent=b.get('model') if b['kind']=='decision' else b.get('parent')
        fields=(self.key(b['id']),self.key(b['key']),self.key(b['experiment']),b['round'],
                {'contribution':1,'model':2,'decision':3}[b['kind']],self.key(parent),bytes.fromhex(b['hash']),
                bytes.fromhex(b['explanation_hash']) if b['kind']=='decision' else bytes(32),[self.key(r) for r in refs])
        self.transact(self.contract.functions.anchor(fields,metadata(b),bytes.fromhex(envelope['signature'].removeprefix('0x'))))
        return self.get(b['id'])['receipt']
