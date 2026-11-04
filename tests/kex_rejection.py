#!/usr/bin/env python3
"""MIT. Send public malformed X25519 inputs to a local disposable SSH fixture.

No login, secrets or encrypted transport. The caller must also verify the
server's specific rejection log; a closed connection alone is not a pass.
"""
import os
import socket
import struct


def string(value):
    return struct.pack('>I', len(value)) + value


def packet(payload):
    padding = 8 - ((len(payload) + 5) % 8)
    if padding < 4:
        padding += 8
    return struct.pack('>IB', len(payload) + padding + 1, padding) + payload + os.urandom(padding)


def reject_public_point(port, point):
    with socket.create_connection(('127.0.0.1', port), timeout=30) as conn:
        conn.settimeout(30)
        conn.sendall(b'SSH-2.0-ELKS_public_KEX_probe\r\n')
        banner = bytearray()
        while not banner.endswith(b'\n'):
            b = conn.recv(1)
            if not b or len(banner) >= 255:
                raise RuntimeError('Missing or oversized SSH banner')
            banner.extend(b)
        if not banner.startswith(b'SSH-2.0-'):
            raise RuntimeError('Unexpected SSH version')

        def exact(length, allow_eof=False):
            data = bytearray()
            while len(data) < length:
                chunk = conn.recv(length - len(data))
                if not chunk:
                    if not data and allow_eof:
                        return None
                    raise RuntimeError('Truncated SSH packet')
                data.extend(chunk)
            return bytes(data)

        def receive():
            head = exact(4, allow_eof=True)
            if head is None:
                return None
            length = struct.unpack('>I', head)[0]
            if not 6 <= length <= 35000:
                raise RuntimeError('Invalid plaintext packet size')
            body = exact(length)
            padding = body[0]
            if padding < 4 or padding >= length - 1:
                raise RuntimeError('Invalid plaintext padding')
            return body[1:-padding]

        initial = receive()
        if not initial or initial[0] != 20:
            raise RuntimeError('Expected server KEXINIT')
        algorithms = [b'curve25519-sha256', b'ssh-ed25519',
                      b'chacha20-poly1305@openssh.com']
        lists = [algorithms[0], algorithms[1], algorithms[2], algorithms[2],
                 b'hmac-sha2-256', b'hmac-sha2-256', b'none', b'none', b'', b'']
        init = b'\x14' + os.urandom(16) + b''.join(string(v) for v in lists) + b'\0' * 5
        conn.sendall(packet(init) + packet(b'\x1e' + string(point)))
        messages = []
        while len(messages) < 8:
            try:
                response = receive()
            except ConnectionResetError:
                response = None
            if response is None:
                return {'closed': True, 'messages': messages,
                        'reached_newkeys': 21 in messages, 'point_bytes': len(point)}
            messages.append(response[0])
            if response[0] in (21, 31):
                raise RuntimeError('Server accepted malformed public point')
        raise RuntimeError('Unexpected messages instead of KEX rejection')
