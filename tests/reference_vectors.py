#!/usr/bin/env python3
"""MIT. Reproduce public SSH ChaCha20-Poly1305 vectors independently.

Development only: requires Python cryptography on the host. All-zero public
key and fixed messages are test fixtures, never production keys or entropy.
Uses the OpenSSH PROTOCOL.chacha20poly1305 construction: header key second,
body key first, 64-bit big-endian packet number and little-endian block count.
"""
import json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.poly1305 import Poly1305


def stream(sequence, counter, data):
    nonce = counter.to_bytes(8, 'little') + sequence.to_bytes(8, 'big')
    cipher = Cipher(algorithms.ChaCha20(bytes(32), nonce), mode=None).encryptor()
    return cipher.update(data) + cipher.finalize()


plain = bytes([0,0,0,12, 8,1,2,3,4,5,6,7,8,9,10,11])
vectors = {}
for sequence in (0, 65535, 65536, 0xffffffff):
    polykey = stream(sequence, 0, bytes(32))
    encrypted = stream(sequence, 0, plain[:4]) + stream(sequence, 1, plain[4:])
    vectors[str(sequence)] = (encrypted + Poly1305.generate_tag(polykey, encrypted)).hex()
print(json.dumps(vectors, indent=2))
