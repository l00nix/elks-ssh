#!/usr/bin/env python3
"""MIT. Test a freshly built private PPC-shaped image in isolated QEMU.
Never uses or emits hardware provisioning material. All temporary state and
keys belong only to this test and are discarded with its private directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time

from private_candidate import build
from fixture import generate, record


def run(args):
    args.out.mkdir(parents=True,exist_ok=False)
    result=dict(status='failed',hardware=False,runtime_entropy_helper=False,
                temporary_test_keys_only=True,production_ready=False)
    with tempfile.TemporaryDirectory(prefix='esh-private-image-') as tmp:
        temp=Path(tmp);instance=temp/'instance'
        build(args.image,args.server,args.check,args.helper,args.mfs,instance)
        disk=instance/'sshtrial.img'
        def fs(*words):
            return subprocess.check_output([str(args.mfs),str(disk),*map(str,words)])
        initial=fs('cat','/root/rngtest/state')
        opts=fs('cat','/bootopts')+b'\nconsole=ttyS0,19200 3\n'
        if len(opts)>1023:raise RuntimeError('Bootopts too long')
        (temp/'bootopts').write_bytes(opts)
        fs('cp',temp/'bootopts','/bootopts')
        serial=temp/'serial'
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
        (instance/'test_hosts').write_bytes(('[127.0.0.1]:%d '%port).encode()+(instance/'host.pub').read_bytes())
        transcript=bytearray();proc=None
        try:
            with (args.out/'qemu.log').open('w') as log:
                proc=subprocess.Popen(['qemu-system-i386','-machine','pc','-cpu','486',
                    '-accel','tcg,one-insn-per-tb=on','-m','16M','-display','none','-monitor','none',
                    '-serial','unix:%s,server=on,wait=off'%serial,
                    '-netdev','user,id=test,restrict=on,hostfwd=tcp:127.0.0.1:%d-:2222'%port,
                    '-device','ne2k_isa,irq=5,netdev=test',
                    '-drive','file=%s,format=raw,if=ide,cache=writethrough,werror=report,rerror=report'%disk,
                    '-boot','c'],stdout=log,stderr=log)
                deadline=time.monotonic()+15
                while not serial.exists():
                    if time.monotonic()>deadline or proc.poll() is not None:raise RuntimeError('QEMU did not start')
                    time.sleep(.05)
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.connect(str(serial));conn.settimeout(.25)
                    deadline=time.monotonic()+90
                    while b'login:' not in transcript:
                        if time.monotonic()>deadline:raise RuntimeError('Autostart boot did not reach login')
                        try:part=conn.recv(8192)
                        except socket.timeout:continue
                        if not part:raise RuntimeError('Boot console disconnected')
                        transcript.extend(part)
                    # No console login or network/source setup commands: the
                    # candidate's own DHCP and SSH startup must do all the work.
                    time.sleep(2)
                    command=['ssh','-F','/dev/null','-v','-p',str(port),'-i',str(instance/'clientkey'),
                        '-oBatchMode=yes','-oIdentitiesOnly=yes','-oIdentityAgent=none',
                        '-oStrictHostKeyChecking=yes','-oUserKnownHostsFile='+str(instance/'test_hosts'),
                        '-oGlobalKnownHostsFile=/dev/null','-oConnectTimeout=300',
                        'root@127.0.0.1','ps; cat /etc/issue; echo SSH_CANDIDATE_OK']
                    completed=subprocess.run(command,capture_output=True,timeout=600)
                    (args.out/'command.txt').write_bytes(completed.stdout)
                    # Paths and ephemeral public fingerprints are not secrets;
                    # normalize private host paths before storing diagnostics.
                    (args.out/'ssh.txt').write_bytes(completed.stderr.replace(str(temp).encode(),b'<temporary>'))
                    output=completed.stdout
                    if completed.returncode or b'SSH_CANDIDATE_OK' not in output or b'ELKS 0.9.2' not in output:
                        raise RuntimeError('Autostart SSH command failed')
                    if b'telnetd' in output or b'ftpd' in output:
                        raise RuntimeError('Plaintext login service still running')
                    if not re.search(rb'^\s*\d+.*ktcp',output,re.M) or not re.search(rb'^\s*\d+.*sshtrial',output,re.M):
                        raise RuntimeError('Expected network/server processes missing')
                    result.update(ssh_exit=0,autostart_login_passed=True,ps_and_issue_passed=True,
                                  plaintext_services_absent=True,strict_pinned_host_verification=True)
            result['status']='passed'
        except Exception:
            result['error']='Candidate boot/login validation failed; inspect local diagnostics'
        finally:
            if proc and proc.poll() is None:proc.kill();proc.wait(timeout=10)
            (args.out/'serial.txt').write_bytes(transcript)
            daemon_log=subprocess.run([str(args.mfs),'-f',str(disk),'cat','/tmp/sshtrial.log'],capture_output=True)
            if daemon_log.returncode==0:(args.out/'server.txt').write_bytes(daemon_log.stdout)
            saved=subprocess.run([str(args.mfs),'-f',str(disk),'cat','/root/rngtest/state'],capture_output=True)
            valid=False
            if saved.returncode==0 and len(saved.stdout)==1024:
                count=int.from_bytes(saved.stdout[8:12],'big')
                if 2<=count<=32:
                    k,v=initial[12:44],initial[44:76]
                    for _ in range(count):discard,k,v=generate(k,v)
                    valid=saved.stdout==record(k,v,count)
                    result['persistent_generation']=count
            result['state_matches_reference']=valid
            if not valid:result['status']='failed'
            result['source_unchanged']=hashlib.sha256(args.image.read_bytes()).hexdigest()=='13fe346b6ca0a4f877c6c925051e4c433e2a899bcd8522e136a5d2fffd2df508'
            if not result['source_unchanged']:result['status']='failed'
    (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('image','server','check','helper','mfs','out'):
        p.add_argument('--'+name,required=True,type=lambda s:Path(s).resolve())
    result=run(p.parse_args());print(json.dumps(result,indent=2))
    raise SystemExit(result['status']!='passed')
