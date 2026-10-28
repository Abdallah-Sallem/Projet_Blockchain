"""Append-only simulator with shared business validation for EVM adapter."""
import json
import re
from datetime import datetime, timezone
from .canonical import metadata, digest
from .identity import recover
from .storage import connect


class Unavailable(RuntimeError):
    pass


def validate(envelope, identities, lookup):
    b = envelope['body']
    author = recover(envelope)
    actor = b['actor']
    if identities.get(actor, '').lower() != author.lower() or envelope['author'].lower() != author.lower():
        raise ValueError('unauthorized_author')
    if b['schema'] != 1 or b['kind'] not in ('contribution', 'model', 'decision'):
        raise ValueError('invalid_schema')
    common={'schema','kind','id','key','actor','experiment','round','timestamp','hash'}
    fields={'contribution':{'samples','parent','privacy','training','metrics'},
            'model':{'parent','accepted','rejected','strategy','configuration','metrics'},
            'decision':{'model','explanation_hash','case','probability','validation'}}
    if set(b) != common | fields[b['kind']]:
        raise ValueError('unexpected_or_missing_fields')
    if not b['id'] or not b['key'] or not b['experiment'] or not b['timestamp']:
        raise ValueError('invalid_identifier')
    datetime.fromisoformat(b['timestamp'])
    if type(b['round']) is not int or b['round'] < 0:
        raise ValueError('invalid_round')
    for key in ('hash', 'explanation_hash'):
        if key in b and not re.fullmatch('[0-9a-f]{64}', b[key]):
            raise ValueError('invalid_hash')
    if b['kind'] == 'contribution':
        if not actor.startswith('clinic-') or type(b['samples']) is not int or b['samples'] < 1:
            raise ValueError('invalid_contribution')
        if not isinstance(b['privacy'], dict) or not isinstance(b['training'], dict):
            raise ValueError('invalid_configuration')
        parent = lookup(b['parent'])
        if not parent or parent['body']['kind'] != 'model' or parent['body']['experiment'] != b['experiment'] or parent['body']['round'] != b['round']-1:
            raise ValueError('invalid_parent')
    elif b['kind'] == 'model':
        if actor != 'server':
            raise ValueError('unauthorized_model_writer')
        if b['round'] == 0:
            if b['parent'] is not None or b['accepted'] or b['rejected']:
                raise ValueError('invalid_root')
        else:
            parent = lookup(b['parent'])
            if not parent or parent['body']['kind'] != 'model' or parent['body']['round'] != b['round']-1 or parent['body']['experiment'] != b['experiment']:
                raise ValueError('invalid_parent')
            refs = b['accepted'] + list(b['rejected'])
            if not b['accepted'] or len(set(refs)) != len(refs):
                raise ValueError('invalid_outcomes')
            actors = set()
            for ref in refs:
                c = lookup(ref)
                if not c or c['body']['kind'] != 'contribution' or c['body']['round'] != b['round'] or c['body']['experiment'] != b['experiment'] or c['body']['parent'] != b['parent']:
                    raise ValueError('invalid_contribution_reference')
                if c['body']['actor'] in actors:
                    raise ValueError('duplicate_clinic')
                actors.add(c['body']['actor'])
            if any(not reason for reason in b['rejected'].values()):
                raise ValueError('missing_rejection_reason')
    else:
        model = lookup(b['model'])
        if not actor.startswith('clinic-') or not model or model['body']['kind'] != 'model' or model['body']['hash'] != b['hash'] or model['body']['experiment'] != b['experiment'] or model['body']['round'] != b['round']:
            raise ValueError('invalid_decision_model')
        if not 0 <= b['probability'] <= 1 or b['validation'] != 'educational_simulation' or not re.fullmatch('[0-9a-f]{32}', b['case']):
            raise ValueError('invalid_decision')
    metadata(envelope)  # reject nonfinite metadata


class LedgerQueries:
    def history(self, key):
        return [r for r in self.records() if r['body']['key'] == key]

    def verify_model(self, model_hash):
        return next((r for r in reversed(self.records()) if r['body']['kind'] == 'model' and r['body']['hash'] == model_hash), None)

    def verify_decision(self, record_id, model_hash, explanation_bytes):
        r = self.get(record_id)
        return bool(r and r['body']['kind'] == 'decision' and r['body']['hash'] == model_hash
                    and r['body']['explanation_hash'] == digest(explanation_bytes) and self.verify_model(model_hash))

    def provenance(self, record_id):
        r = self.get(record_id)
        if not r:
            raise KeyError(record_id)
        b = r['body']
        refs = ([b['model']] if b['kind'] == 'decision' else
                (([b['parent']] if b['parent'] else []) + b['accepted'] + list(b['rejected'])) if b['kind'] == 'model' else [])
        return {'record': r, 'children': [self.provenance(x) for x in refs]}


class LocalLedger(LedgerQueries):
    label = 'Registre local chaîné (simulateur)'

    def __init__(self, home, identities):
        from pathlib import Path
        self.home = Path(home)
        self.identities = identities
        self.db = connect(self.home / 'ledger.sqlite')
        self.db.execute('''CREATE TABLE IF NOT EXISTS records(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                        id TEXT UNIQUE, envelope TEXT, previous TEXT, chain_hash TEXT UNIQUE)''')
        self.db.commit()

    def check(self):
        if (self.home / 'ledger.offline').exists():
            raise Unavailable('ledger_unavailable')
        previous = '0'*64
        for r in self.db.execute('SELECT * FROM records ORDER BY seq'):
            if r['previous'] != previous or digest(bytes.fromhex(previous) + r['envelope'].encode()) != r['chain_hash']:
                raise Unavailable('ledger_integrity_failure')
            previous = r['chain_hash']

    @staticmethod
    def decode(row):
        if not row:
            return None
        result = json.loads(row['envelope'])
        result['receipt'] = {'id': row['chain_hash'], 'sequence': row['seq'], 'confirmed': True, 'adapter': 'local-simulator'}
        return result

    def get(self, record_id):
        self.check()
        return self.decode(self.db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone())

    def records(self):
        self.check()
        return [self.decode(r) for r in self.db.execute('SELECT * FROM records ORDER BY seq')]

    def anchor(self, envelope):
        self.check()
        encoded = metadata(envelope).decode()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old = self.db.execute('SELECT * FROM records WHERE id=?', (envelope['body']['id'],)).fetchone()
            if old:
                if old['envelope'] != encoded:
                    raise ValueError('conflicting_duplicate')
                return self.decode(old)['receipt']
            validate(envelope, self.identities, self.get)
            last = self.db.execute('SELECT chain_hash FROM records ORDER BY seq DESC LIMIT 1').fetchone()
            previous = last[0] if last else '0'*64
            h = digest(bytes.fromhex(previous) + encoded.encode())
            self.db.execute('INSERT INTO records(id,envelope,previous,chain_hash) VALUES (?,?,?,?)',
                            (envelope['body']['id'], encoded, previous, h))
        return self.get(envelope['body']['id'])['receipt']


def body(kind, record_id, actor, experiment, round_id, **kwargs):
    return dict(schema=1, kind=kind, id=record_id, key=kwargs.pop('key', record_id), actor=actor,
                experiment=experiment, round=round_id, timestamp=datetime.now(timezone.utc).isoformat(), **kwargs)
