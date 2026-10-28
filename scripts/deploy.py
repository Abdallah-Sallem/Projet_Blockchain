import argparse
import json
from pathlib import Path
from web3 import Web3
from eth_account import Account


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rpc',default='http://127.0.0.1:8545')
    args=parser.parse_args()
    w3=Web3(Web3.HTTPProvider(args.rpc))
    if not w3.is_connected():
        raise SystemExit('RPC unavailable. Run: cd contracts; npm run chain')
    # Development only: fund a newly generated gateway from an unlocked local account.
    gateway=Account.create()
    fund=w3.eth.send_transaction({'from':w3.eth.accounts[0],'to':gateway.address,'value':w3.to_wei(100,'ether')})
    w3.eth.wait_for_transaction_receipt(fund)
    artifact=json.loads(Path('contracts/artifacts/FedTrace.json').read_text())
    factory=w3.eth.contract(abi=artifact['abi'],bytecode=artifact['bytecode'])
    tx=factory.constructor().build_transaction({'from':gateway.address,'nonce':0,'chainId':w3.eth.chain_id})
    signed=gateway.sign_transaction(tx)
    receipt=w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.raw_transaction))
    assert receipt.status==1
    path=Path('runtime/evm/deployment.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'rpc':args.rpc,'address':receipt.contractAddress,'key':gateway.key.hex(),'deployment_tx':receipt.transactionHash.hex()},indent=2))
    print('Development contract deployed: '+receipt.contractAddress+'; credentials saved outside source control.')


if __name__=='__main__': main()
