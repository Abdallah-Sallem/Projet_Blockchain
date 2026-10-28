import os
from pathlib import Path
from eth_account import Account
from eth_account.messages import encode_defunct
from .canonical import metadata, digest


def identity(home, name):
    path = Path(home) / 'keys' / (name + '.key')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        key = Account.create().key.hex()
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(key)
    return Account.from_key(path.read_text().strip())


def sign(body, account):
    msg = encode_defunct(primitive=bytes.fromhex(digest(metadata(body))))
    return {'body': body, 'author': account.address,
            'signature': account.sign_message(msg).signature.hex()}


def recover(envelope):
    msg = encode_defunct(primitive=bytes.fromhex(digest(metadata(envelope['body']))))
    return Account.recover_message(msg, signature=envelope['signature'])
