"""MIT. Independent Python HMAC_DRBG oracle using PUBLIC TEST INPUT only.

This is not a production seed/provisioning tool.
"""
import hashlib
import hmac


def update(k, v, seed=b''):
    k = hmac.digest(k, v+b'\0'+seed, 'sha256')
    v = hmac.digest(k, v, 'sha256')
    if seed:
        k = hmac.digest(k, v+b'\1'+seed, 'sha256')
        v = hmac.digest(k, v, 'sha256')
    return k, v


def initial():
    return update(bytes(32), b'\1'*32, bytes(range(48)))


def generate(k, v):
    out = hmac.digest(k, v, 'sha256')
    k, v = update(k, out)
    return out, k, v


def record(k, v, count=0):
    header = b'ESHRNG01'+count.to_bytes(4, 'big')+k+v+bytes(916)
    assert len(header) == 992
    return header+hashlib.sha256(header).digest()


def expected(n):
    k, v = initial()
    outputs = []
    for _ in range(n):
        out, k, v = generate(k, v)
        outputs.append(out.hex())
    return outputs, record(k, v, n)
