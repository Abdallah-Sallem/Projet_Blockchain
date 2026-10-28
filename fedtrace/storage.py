import json
import os
import sqlite3
import uuid
from pathlib import Path
import numpy as np
from .canonical import metadata


def connect(path):
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    return db


class Store:
    def __init__(self, home):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        if os.name != 'nt':
            self.home.chmod(0o700)
        self.db = connect(self.home / 'metadata.sqlite')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS objects(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, envelope TEXT NOT NULL,
          dependencies TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER DEFAULT 0,
          next_at REAL DEFAULT 0, receipt TEXT, error TEXT);
        ''')

    def put(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO objects VALUES (?,?)', (key, metadata(value).decode()))

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM objects WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def path(self, name):
        path = (self.home / 'artifacts' / name).resolve()
        if not path.is_relative_to((self.home / 'artifacts').resolve()):
            raise ValueError('unsafe_path')
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_bytes(self, name, content):
        path = self.path(name)
        tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        with open(tmp, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return name

    def save_model(self, name, weights):
        import io
        buf = io.BytesIO()
        np.savez(buf, **weights)
        self.write_bytes(name, buf.getvalue())
        return name

    def load_model(self, name):
        with np.load(self.path(name), allow_pickle=False) as f:
            return {k: f[k].copy() for k in f.files}
