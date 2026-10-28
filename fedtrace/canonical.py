"""Versioned canonical bytes; never hash framework checkpoint serialization."""
import hashlib
import json
import struct
from collections.abc import Mapping
import numpy as np


def metadata(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def field(value):
    return struct.pack('<Q', len(value)) + value


def tensor_bytes(weights, kind='model'):
    if kind not in ('model', 'update') or not isinstance(weights, Mapping) or not weights:
        raise ValueError('invalid_tensor_document')
    if any(not isinstance(name,str) or not name for name in weights):
        raise ValueError('invalid_parameter_name')
    result = b'FedTrace\x00v1' + field(kind.encode()) + struct.pack('<Q', len(weights))
    for name in sorted(weights):
        if not isinstance(name, str) or not name:
            raise ValueError('invalid_parameter_name')
        a = np.asarray(weights[name])
        if a.dtype.kind not in 'fiu' or a.dtype.itemsize not in (1, 2, 4, 8):
            raise ValueError('unsupported_dtype')
        if not np.isfinite(a).all():
            raise ValueError('non_finite_tensor')
        shape = a.shape
        a = np.ascontiguousarray(a.astype(a.dtype.newbyteorder('<'), copy=False)).reshape(shape)
        result += field(name.encode('utf-8')) + field(a.dtype.str.encode('ascii'))
        result += struct.pack('<Q', a.ndim) + b''.join(struct.pack('<Q', s) for s in a.shape)
        result += field(a.tobytes(order='C'))
    return result


def model_hash(weights, kind='model'):
    return digest(tensor_bytes(weights, kind))
