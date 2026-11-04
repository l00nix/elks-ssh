#!/usr/bin/env python3
"""MIT. Convert an ELKS FAT test fixture into a private MINIX test image.
Uses upstream ELKS mfs/setboot and Make.devices; does not rebuild the OS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    if args.out.exists():
        raise SystemExit('Output already exists; choose a new test-image path')
    before = sha(args.fat_image)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='esh-fs-') as directory:
        root = Path(directory) / 'root'
        root.mkdir(mode=0o755)
        subprocess.run(['mcopy', '-s', '-i', str(args.fat_image), '::*', str(root)], check=True)
        for path in root.rglob('*'):
            if len(path.name.encode()) > 14:
                raise RuntimeError('Fixture filename exceeds MINIX limit: '+str(path.relative_to(root)))
        # FAT metadata cannot represent the required ownership/modes. Set a
        # controlled fixture policy; mfs defaults all owners/groups to root.
        for path in root.rglob('*'):
            path.chmod(0o755 if path.is_dir() or path.parent == root/'bin' else 0o644)
        (root/'tmp').chmod(0o1777)
        (root/'root').chmod(0o700)
        shutil.rmtree(root/'dev')
        (root/'dev').mkdir(mode=0o755)
        subprocess.run([str(args.mfs), str(args.out), 'genfs', '-1', '-n14',
                        '-i2048', '-s31752', str(root)], check=True)
        subprocess.run(['make', '-s', '-f', str(args.devices),
                        'MKDEV='+shlex.quote(str(args.mfs))+' '+shlex.quote(str(args.out))+' mknod'], check=True)
        subprocess.run([str(args.setboot), str(args.out), '-B63,16,63', str(args.boot)], check=True)
        subprocess.run([str(args.mfs), str(args.out), 'ls', '-ld', '/', '/root', '/etc'], check=True)
    assert sha(args.fat_image) == before
    report = {'source_fat_sha256': before, 'minix_sha256': sha(args.out),
              'boot_sha256': sha(args.boot), 'device_manifest_sha256': sha(args.devices),
              'kernel_rebuilt': False, 'source_unchanged': True, 'minix_name_length': 14}
    args.out.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for name in ['fat-image','mfs','setboot','devices','boot','out']:
        p.add_argument('--'+name, type=lambda s:Path(s).resolve(), required=True)
    run(p.parse_args())
