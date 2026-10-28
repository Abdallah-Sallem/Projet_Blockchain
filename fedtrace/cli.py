import argparse
import json
import os
from .service import Service


def main():
    parser=argparse.ArgumentParser(description='FedTrace synthetic academic prototype')
    parser.add_argument('command',choices=['demo','serve','token','status','resume'])
    parser.add_argument('--home',default=os.getenv('FEDTRACE_HOME','runtime/demo'))
    parser.add_argument('--rounds',type=int,default=3)
    parser.add_argument('--clinics',type=int,default=3)
    parser.add_argument('--epochs',type=int,default=6)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--strategy',choices=['robust','fedavg'],default='robust')
    parser.add_argument('--poison',action='store_true')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    os.environ['FEDTRACE_HOME']=args.home
    from .api import service
    s=service()
    if args.command=='demo':
        s.run(rounds=args.rounds,clinics=args.clinics,epochs=args.epochs,seed=args.seed,strategy=args.strategy,poison=args.poison)
        decision=s.infer([.4,-.3,.8,.2,-.1,.5])
        print(json.dumps({'decision':decision,'verification':s.verify(decision['id']),
                          'provenance':s.ledger.provenance(decision['id'])},ensure_ascii=False,indent=2))
    elif args.command=='serve':
        import uvicorn
        print('Demo API token (local custodian / clinic-1): '+s.store.get('api_token'))
        uvicorn.run('fedtrace.api:app',host='127.0.0.1',port=args.port)
    elif args.command=='token':
        print(s.store.get('api_token'))
    elif args.command=='resume':
        print(json.dumps(s.advance(force=True)))
    else:
        print(json.dumps(s.status(),indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
