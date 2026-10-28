import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from .service import Service
from .ledger import Unavailable

HOME = os.getenv('FEDTRACE_HOME','runtime/demo')
DEMO = os.getenv('FEDTRACE_DEMO','0') == '1'
lock = asyncio.Lock()


def service():
    s = Service(HOME)
    if os.getenv('FEDTRACE_LEDGER') == 'evm':
        from .evm import EvmLedger
        s.ledger = EvmLedger.from_env(s.store.get('identities'))
        s.outbox.ledger = s.ledger
    return s


def call(fn):
    s = service()
    try:
        return fn(s)
    finally:
        s.store.db.close()
        if hasattr(s.ledger,'db'):
            s.ledger.db.close()


async def execute(fn):
    async with lock:
        try:
            return await asyncio.to_thread(call,fn)
        except Unavailable as exc:
            raise HTTPException(503,detail={'reason':str(exc)})
        except (ValueError,KeyError) as exc:
            raise HTTPException(409,detail={'reason':str(exc)})


async def authorized(authorization: str = Header(default='')):
    expected = await execute(lambda s:s.store.get('api_token'))
    if not secrets.compare_digest(authorization, 'Bearer '+expected):
        raise HTTPException(401,detail={'reason':'unauthorized'})


async def tick():
    while True:
        try:
            await execute(lambda s:s.advance())
        except Exception:
            # Retain and expose error, never mark work confirmed after failure.
            import traceback
            message = traceback.format_exc()
            await execute(lambda s:s.store.put('worker_error',message))
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(tick())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title='FedTrace',lifespan=lifespan)


class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clinics:int = Field(default=3,ge=3,le=12)
    rounds:int = Field(default=3,ge=1,le=100)
    epochs:int = Field(default=6,ge=1,le=1000)
    seed:int = 42
    strategy:str = 'robust'
    poison:bool = False


class Case(BaseModel):
    model_config = ConfigDict(extra='forbid')
    features:list[float]


@app.get('/api/status')
async def status():
    return await execute(lambda s:{**s.status(),'demo':DEMO,'worker_error':s.store.get('worker_error')})


@app.post('/api/experiments',dependencies=[Depends(authorized)])
async def experiment(config:Configuration):
    return await execute(lambda s:s.configure(**config.model_dump()))


@app.post('/api/diagnose',dependencies=[Depends(authorized)])
async def diagnose(case:Case):
    # Demo bearer credential authorizes the custodial clinic-1 identity only.
    return await execute(lambda s:s.infer(case.features,clinic='clinic-1'))


@app.get('/api/decisions/{decision}/verify')
async def verify(decision:str):
    return await execute(lambda s:s.verify(decision))


@app.get('/api/decisions/{decision}/explanation')
async def explanation(decision:str):
    def load(s):
        stored=s.store.get('decision:'+decision)
        if not stored:
            raise KeyError(decision)
        return s.store.path(stored['path']).read_bytes()
    exact=await execute(load)
    return Response(content=exact,media_type='application/json',
                    headers={'Content-Disposition':'attachment; filename="explanation.json"'})


@app.get('/api/provenance/{record}')
async def provenance(record:str):
    return await execute(lambda s:s.ledger.provenance(record))


@app.get('/api/history/{key}')
async def history(key:str):
    return await execute(lambda s:s.ledger.history(key))


@app.get('/api/benchmarks')
async def benchmarks():
    import json
    path = Path('benchmarks/summary.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


@app.post('/api/demo/ledger/{state}',dependencies=[Depends(authorized)])
async def ledger_state(state:str):
    if not DEMO or state not in ('online','offline'):
        raise HTTPException(403,detail={'reason':'demo_control_disabled'})
    def update(s):
        flag = s.store.home/'ledger.offline'
        if state == 'offline':
            flag.touch()
        else:
            flag.unlink(missing_ok=True)
        return {'state':state}
    return await execute(update)


if Path('frontend/dist').exists():
    app.mount('/',StaticFiles(directory='frontend/dist',html=True),name='frontend')
