#!/usr/bin/env python3
"""MIT. Experimental host-side bundle creation, NOT a deployment installer.

Never changes an ELKS image, a running consumer, or a previous bundle. No seed
argument/file is accepted. Recovery creates fresh material by the same path.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import subprocess


def validate(record):
    if (len(record) != 1024 or record[:12] != b'ESHRNG01' + bytes(4)
            or any(record[76:992])
            or hashlib.sha256(record[:992]).digest() != record[992:]):
        raise ValueError('Provisioning helper returned an invalid record')


def create_bundle(directory, helper):
    # Inherited by helper. Python does not promise to erase all temporary
    # copies from RAM; run only on a trusted installation host.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    directory = Path(directory)
    helper = Path(helper).resolve(strict=True)
    # Exclusive creation refuses existing directories and symlinks, including
    # an incomplete previous attempt. Never remove or replace those implicitly.
    os.mkdir(directory, 0o700)
    dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = os.fstat(dfd)
        if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
            raise ValueError('Bundle directory is not private')
        seed = os.urandom(48)
        result = subprocess.run([str(helper)], input=seed, capture_output=True,
                                timeout=15, check=False)
        del seed
        if result.returncode or result.stderr:
            # Do not echo a helper's output: it could contain secret material.
            raise RuntimeError('Provisioning helper failed; bundle is incomplete')
        record = result.stdout
        validate(record)

        def write(name, value):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=dfd)
            with os.fdopen(fd, 'wb') as file:
                file.write(value)
                file.flush()
                os.fsync(file.fileno())

        write('state', record)
        fd = os.open('state', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
        with os.fdopen(fd, 'rb') as file:
            if file.read() != record:
                raise RuntimeError('Bundle state readback failed')
        # COMPLETE is written last. It is a local workflow marker, not a
        # signature or a guarantee about a future target's storage durability.
        write('COMPLETE.json', (json.dumps({
            'format': 'ESHRNG01', 'generation': 0,
            'status': 'experimental-host-bundle-only',
            'source': '48 bytes from host os.urandom',
            'generator': 'pinned BearSSL 0.6 HMAC_DRBG SHA-256',
            'installation': 'offline trusted media; consumers must be stopped',
            'reuse': 'one device and one installation only; never clone or restore',
            'ssh_ready': False,
        }, indent=2) + '\n').encode())
        os.fsync(dfd)
    finally:
        os.close(dfd)
    # Persist the new directory entry on the installation host as well.
    pfd = os.open(directory.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(pfd)
    finally:
        os.close(pfd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path,
                        help='New private directory outside repositories/cloud sync')
    parser.add_argument('--helper', required=True, type=Path,
                        help='Trusted locally built seed-record executable')
    args = parser.parse_args()
    try:
        create_bundle(args.output, args.helper)
    except Exception:
        # No exception payloads from secret-bearing subprocesses in logs.
        parser.exit(1, 'Bundle creation failed. Do not use an incomplete bundle; '
                    'existing files were not replaced.\n')
    print('Private experimental bundle created. Not installed; not SSH-ready.')
