import json
import time
from .canonical import metadata
from .ledger import Unavailable


class Outbox:
    def __init__(self, store, ledger):
        self.store, self.ledger = store, ledger

    def enqueue(self, envelope, dependencies=()):
        b = envelope['body']
        encoded, deps = metadata(envelope).decode(), metadata(list(dependencies)).decode()
        with self.store.db:
            old = self.store.db.execute('SELECT envelope,dependencies FROM outbox WHERE id=?', (b['id'],)).fetchone()
            if old and (old[0], old[1]) != (encoded, deps):
                raise ValueError('conflicting_outbox_id')
            self.store.db.execute('INSERT OR IGNORE INTO outbox(id,envelope,dependencies,state) VALUES (?,?,?,?)',
                                  (b['id'], encoded, deps, 'pending'))

    def rows(self):
        return [dict(r) for r in self.store.db.execute('SELECT * FROM outbox ORDER BY rowid')]

    def confirmed(self, record_id):
        row = self.store.db.execute('SELECT state FROM outbox WHERE id=?', (record_id,)).fetchone()
        return bool(row and row[0] == 'confirmed')

    def flush(self, force=False):
        for row in self.rows():
            if row['state'] in ('confirmed', 'failed') or (not force and row['next_at'] > time.time()):
                continue
            if not all(self.confirmed(x) for x in json.loads(row['dependencies'])):
                continue
            try:
                envelope = json.loads(row['envelope'])
                existing = self.ledger.get(row['id'])
                if existing:
                    if {k: existing[k] for k in ('body', 'author', 'signature')} != envelope:
                        raise ValueError('conflicting_duplicate')
                    receipt = existing['receipt']
                else:
                    with self.store.db:
                        self.store.db.execute("UPDATE outbox SET state='submitted' WHERE id=?", (row['id'],))
                    receipt = self.ledger.anchor(envelope)
                if not receipt['confirmed']:
                    raise Unavailable('confirmation_pending')
                with self.store.db:
                    self.store.db.execute("UPDATE outbox SET state='confirmed',receipt=?,error=NULL WHERE id=?", (metadata(receipt).decode(), row['id']))
            except (Unavailable, ConnectionError, TimeoutError) as exc:
                with self.store.db:
                    self.store.db.execute("UPDATE outbox SET state='pending',attempts=attempts+1,next_at=?,error=? WHERE id=?",
                                          (time.time()+min(60, 0.5*2**min(row['attempts'], 7)), str(exc), row['id']))
            except ValueError as exc:
                with self.store.db:
                    self.store.db.execute("UPDATE outbox SET state='failed',error=? WHERE id=?", (str(exc), row['id']))
