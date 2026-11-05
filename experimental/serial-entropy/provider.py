#!/usr/bin/env python3
"""MIT. Assisted entropy over a controlled physical cable. Not network-authenticated.

Only counts and public request IDs may be logged. Never log/cache response bytes.
Every provider instance gets a new OS-random public session ID. ELKS receives
that ID as a one-use launch file and maintains its counter in shared state.
"""
import argparse
import binascii
import hashlib
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import termios
import fcntl


class Provider:
    def __init__(self, source=os.urandom):
        self.source = source
        self.session = source(16)
        if len(self.session) != 16:
            raise RuntimeError('OS random source failed')
        self.last = 0
        self.requests = 0
        self._seen = set()

    def answer(self, request):
        if len(request) != 24 or request[:4] != b'ESQ1' or request[4:20] != self.session:
            raise ValueError('Invalid request or different session')
        sequence = struct.unpack('>I', request[20:24])[0]
        if sequence <= self.last or self.requests >= 1024:
            raise ValueError('Repeated request or session limit reached')
        # Reserve before requesting randomness: errors cannot replay this request.
        self.last = sequence
        fresh = self.source(32)
        if len(fresh) != 32:
            raise RuntimeError('OS random source failed')
        digest = hashlib.sha256(fresh).digest()
        if digest in self._seen:
            raise RuntimeError('Repeated random output')
        self._seen.add(digest)
        self.requests += 1
        frame = b'ESR1' + request[4:] + fresh
        return frame + struct.pack('>I', binascii.crc32(frame))

    def bootstrap(self, directory):
        directory.mkdir(mode=0o700)
        for name, data in [('esession', self.session), ('ecounter', self.session + bytes(4))]:
            fd = os.open(directory/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as output:
                output.write(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    endpoint = p.add_mutually_exclusive_group(required=True)
    endpoint.add_argument('--device', help='Dedicated physical serial device, 1200 8N1')
    endpoint.add_argument('--unix', help='Private emulator serial Unix socket')
    p.add_argument('--bootstrap', type=Path, required=True, help='New local directory for public one-use launch files')
    p.add_argument('--baud', type=int, choices=[300,1200,2400,9600], default=1200,
                   help='Physical port speed; must match the target build')
    a = p.parse_args()
    connection = None
    previous = None
    if a.unix:
        connection = socket.socket(socket.AF_UNIX)
        connection.connect(a.unix)
        fd = connection.fileno()
    else:
        fd = os.open(a.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        fcntl.ioctl(fd, termios.TIOCEXCL)
        owners = subprocess.run(['lsof','-t',a.device], capture_output=True, text=True, check=True)
        if set(owners.stdout.split()) != {str(os.getpid())}:
            os.close(fd)
            raise RuntimeError('Serial device has another owner')
        previous = termios.tcgetattr(fd)
        settings = termios.tcgetattr(fd)
        settings[0] = settings[1] = settings[3] = 0
        settings[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
        settings[4] = settings[5] = getattr(termios,'B'+str(a.baud))
        settings[6][termios.VMIN] = settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, settings)
        termios.tcflush(fd, termios.TCIOFLUSH)
    provider = Provider()
    pending = bytearray()
    running = True
    def stop(*unused):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        provider.bootstrap(a.bootstrap)
        print('READY: fresh session; public bootstrap files written; no seed bytes logged', flush=True)
        while running:
            if not select.select([fd], [], [], .5)[0]:
                continue
            chunk = os.read(fd, 128)
            if not chunk:
                if connection:
                    break
                continue
            pending.extend(chunk)
            while len(pending) >= 24:
                request = bytes(pending[:24]); del pending[:24]
                response = provider.answer(request)
                remaining = memoryview(response)
                while remaining:
                    if not select.select([], [fd], [], 2)[1]:
                        raise RuntimeError('Serial output timed out')
                    written = os.write(fd, remaining)
                    if written <= 0:
                        raise RuntimeError('Serial output failed')
                    remaining = remaining[written:]
                del response, remaining
                print('REQUEST %d sequence %d complete' % (provider.requests, provider.last), flush=True)
    finally:
        if previous is not None:
            try:
                termios.tcsetattr(fd, termios.TCSANOW, previous)
            except (OSError, termios.error):
                # An unplugged USB adapter cannot have its settings restored.
                pass
        if connection:
            connection.close()
        else:
            os.close(fd)
        print('STOP: %d requests; restart requires a new bootstrap pair' % provider.requests, flush=True)


if __name__ == '__main__':
    main()
