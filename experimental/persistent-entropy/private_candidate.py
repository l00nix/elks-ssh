#!/usr/bin/env python3
"""MIT. Private PPC SSH experiment, not a production installer/release.

Creates a new image from the exact preserved public fixture. Never boots it.
Use a separate fresh instance for QEMU; never reuse tested state on hardware.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from provision import create_bundle

SOURCE_SHA = '13fe346b6ca0a4f877c6c925051e4c433e2a899bcd8522e136a5d2fffd2df508'
SERVER_SHA = 'f4f1c03f0c0cc824dc1d5f088e11240d1e176506dd0d5bb00fb56c63cd21bfee'
CHECK_SHA = '8999a4d1d0c0d392552249abef333e6902cd81da7da212f513f6b385fa15c264'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(image, server, check, helper, mfs, output):
    if sha(image)!=SOURCE_SHA or sha(server)!=SERVER_SHA or sha(check)!=CHECK_SHA:
        raise RuntimeError('Input does not match the qualified experimental fixture/build')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    create_bundle(output/'rng-bundle',helper)
    disk=output/'sshtrial.img'
    with disk.open('xb') as dst, image.open('rb') as src:
        os.chmod(disk,0o600);shutil.copyfileobj(src,dst)

    def fs(*words):
        return subprocess.check_output([str(mfs),str(disk),*map(str,words)])

    def flush():
        with disk.open('r+b') as f:os.fsync(f.fileno())

    def put(path, data, mode=0o600):
        local=output/'staging-file'
        local.write_bytes(data);local.chmod(mode)
        fs('cp',local,path)
        if fs('cat',path)!=data:raise RuntimeError('Installed file failed readback')
        local.unlink()

    bootopts=fs('cat','/bootopts');kernel=fs('cat','/linux')
    # Remove the byte-printing public probe before introducing secret state.
    fs('rm','/root/rngtest/rngprobe')
    seed_state=(output/'rng-bundle/state').read_bytes()
    put('/root/rngtest/state',seed_state);flush()
    if fs('cat','/root/rngtest/state')!=seed_state:raise RuntimeError('State readback failed')
    fs('rm','/root/rngtest/lock');flush()
    put('/root/rngtest/rngcheck',check.read_bytes(),0o700)
    put('/bin/sshtrial',server.read_bytes(),0o700)

    # addfs preserves mode 700 from the private staging directory. No chmod
    # window on a booted system, and no untrusted file metadata is imported.
    template=output/'template'
    keydir=template/'root/sshtrial';keydir.mkdir(parents=True,mode=0o700)
    keydir.chmod(0o700)
    host=Ed25519PrivateKey.generate();client=Ed25519PrivateKey.generate()
    hostseed=host.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
    hostraw=host.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    def string(value):return struct.pack('>I',len(value))+value
    (keydir/'hostkey').write_bytes(string(b'ssh-ed25519')+string(hostseed+hostraw))
    (keydir/'authkeys').write_bytes(client.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)+b' ppc-test-only\n')
    for name in ('hostkey','authkeys'):(keydir/name).chmod(0o600)
    filelist=output/'filelist'
    filelist.write_text('root/sshtrial\nroot/sshtrial/hostkey\nroot/sshtrial/authkeys\n')
    fs('addfs',filelist,template)
    for name in ('hostkey','authkeys'):
        if fs('cat','/root/sshtrial/'+name)!=(keydir/name).read_bytes():raise RuntimeError('Key install mismatch')
    hostpub=host.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)
    (output/'host.pub').write_bytes(hostpub+b'\n')
    (output/'clientkey').write_bytes(client.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.OpenSSH,serialization.NoEncryption()))
    (output/'clientkey').chmod(0o600)
    (output/'known_hosts').write_bytes(b'[10.0.0.66]:2222 '+hostpub+b'\n')
    (output/'known_hosts').chmod(0o600)

    netcfg=fs('cat','/etc/net.cfg')
    if netcfg.count(b'netstart="telnetd ftpd"')!=1:raise RuntimeError('Unexpected network startup configuration')
    put('/etc/net.cfg',netcfg.replace(b'netstart="telnetd ftpd"',b'netstart=""'),0o644)
    startup=fs('cat','/etc/rc.sys')
    startup+=b'\n# Isolated SSH experiment; public-key-only, no plaintext login daemons.\n'
    # This ELKS configuration disables syslog and does not accept -E.
    startup+=b'/bin/sshtrial -F -p 2222 -r /root/sshtrial/hostkey -D /root/sshtrial </dev/null >/tmp/sshtrial.log 2>&1 &\n'
    put('/etc/rc.sys',startup,0o644)
    put('/root/rngtest/TRIAL',b'Private SSH experiment; do not clone or restore this state.\n')
    flush()
    if fs('cat','/bootopts')!=bootopts or fs('cat','/linux')!=kernel:
        raise RuntimeError('Kernel or hardware boot configuration changed')
    for path,mode in [('/root/rngtest','drwx------'),('/root/sshtrial','drwx------'),
                      ('/root/rngtest/state','-rw-------'),('/root/sshtrial/hostkey','-rw-------'),
                      ('/root/sshtrial/authkeys','-rw-------')]:
        import re
        metadata=fs('ls','-ld',path).decode()
        if not re.search(r'^'+re.escape(mode)+r'\s+\d+\s+\d+\s+0,\s+0\s+',metadata,re.M):
            raise RuntimeError('Private target permissions failed')
    receipt=dict(status='prepared-unbooted',experimental=True,ssh_release_ready=False,
                 source_unchanged=sha(image)==SOURCE_SHA,server_sha256=SERVER_SHA,
                 check_sha256=CHECK_SHA,output_image='sshtrial.img',output_bytes=disk.stat().st_size,
                 output_sha256=sha(disk),runtime_entropy_helper=False,
                 hardware_generation=0,ssh_port=2222,telnet_ftp_autostart=False,
                 kernel_bootopts_preserved=True,private_target_permissions_verified=True)
    if not receipt['source_unchanged']:raise RuntimeError('Source image changed')
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    # Remove redundant staging copies of host private key and seed state.
    # The image is still private and must be retired after transfer/first boot.
    shutil.rmtree(template);shutil.rmtree(output/'rng-bundle');filelist.unlink()
    (output/'connect.sh').write_text('''#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec ssh -F /dev/null -p 2222 -i "$here/clientkey" \\
  -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityAgent=none \\
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$here/known_hosts" \\
  -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=300 root@10.0.0.66 "$@"
''')
    (output/'connect.sh').chmod(0o700)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('image','server','check','helper','mfs','output'):
        p.add_argument('--'+name,required=True,type=lambda s:Path(s).resolve())
    args=p.parse_args()
    if Path(__file__).resolve().parents[2] in args.output.parents:
        p.error('Private hardware candidates must be outside the repository')
    try:
        receipt=build(args.image,args.server,args.check,args.helper,args.mfs,args.output)
    except Exception:
        p.exit(1,'Candidate preparation failed; do not boot an incomplete image.\n')
    print(json.dumps(receipt,indent=2))
