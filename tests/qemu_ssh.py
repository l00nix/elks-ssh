#!/usr/bin/env python3
"""MIT. Disposable QEMU SSH test with fresh host-fed entropy and ephemeral keys.
Never runs on physical serial ports. Requires cryptography, QEMU and mtools.
No private keys, entropy bytes or reusable guest image are retained in outputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EntropyProvider(threading.Thread):
    def __init__(self, path, mode):
        super().__init__(daemon=True)
        self.path, self.mode = path, mode
        self.stop_event = threading.Event()
        self.requests = 0
        self.bytes_sent = 0
        self.error = None

    def run(self):
        try:
            with socket.socket(socket.AF_UNIX) as conn:
                conn.connect(str(self.path)); conn.settimeout(.2)
                pending = bytearray()
                while not self.stop_event.is_set():
                    try:
                        chunk = conn.recv(128)
                    except socket.timeout:
                        continue
                    if not chunk: return
                    pending.extend(chunk)
                    while len(pending) >= 2:
                        request = bytes(pending[:2]); del pending[:2]
                        if request != bytes([2,32]):
                            raise RuntimeError('Unexpected entropy request framing')
                        self.requests += 1
                        if self.mode == 'silent': continue
                        fresh = os.urandom(32)
                        if self.mode == 'short': fresh = fresh[:16]
                        conn.sendall(fresh)
                        self.bytes_sent += len(fresh)
        except Exception as exc:
            if not self.stop_event.is_set(): self.error = str(exc)


def run(args):
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    result = {'status':'failed', 'entropy_mode':args.entropy,
              'server_sha256':sha(args.server), 'image_sha256':sha(args.image),
              'cpu':args.cpu, 'real_hardware':False, 'production_entropy':False,
              'ssh_client':subprocess.run(['ssh','-V'],capture_output=True,text=True).stderr.strip()}
    transcript = bytearray()
    with tempfile.TemporaryDirectory(prefix='esh-ssh-') as directory:
        temp = Path(directory)
        disk = temp/'disk.img'; shutil.copyfile(args.image,disk)
        def put(source, target):
            subprocess.run(['mcopy','-o','-i',str(disk),str(source),'::'+target],check=True)
        opts = subprocess.check_output(['mtype','-i',str(disk),'::/bootopts'])
        opts += b'\nconsole=ttyS0,19200 3\n'
        assert len(opts)<=1023
        (temp/'bootopts').write_bytes(opts); put(temp/'bootopts','/bootopts')
        put(args.server,'/bin/sshtest')
        # Dropbear's private Ed25519 format: SSH string algorithm, then
        # a 64-byte string containing the fresh seed followed by its public key.
        host = Ed25519PrivateKey.generate()
        seed = host.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
        public = host.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        def string(value): return struct.pack('>I',len(value))+value
        (temp/'hostkey').write_bytes(string(b'ssh-ed25519')+string(seed+public))
        os.chmod(temp/'hostkey',0o600); put(temp/'hostkey','/etc/hostkey')
        client = Ed25519PrivateKey.generate()
        (temp/'clientkey').write_bytes(client.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.OpenSSH,serialization.NoEncryption()))
        os.chmod(temp/'clientkey',0o600)
        clientpub=client.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)
        (temp/'authorized_keys').write_bytes(clientpub+b' test-only\n')
        put(temp/'authorized_keys','/etc/authorized_keys')
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0)); port=reserve.getsockname()[1]
        hostpub=host.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)
        (temp/'known_hosts').write_bytes(('[127.0.0.1]:%d '%port).encode()+hostpub+b'\n')
        serial,entropy,qmp=temp/'serial',temp/'entropy',temp/'qmp'
        proc=None; provider=None
        try:
            with (out/'qemu.log').open('w') as log:
                proc=subprocess.Popen(['qemu-system-i386','-machine','pc','-cpu',args.cpu,
                    '-accel','tcg,one-insn-per-tb=on','-m','16M','-display','none','-monitor','none',
                    '-serial',f'unix:{serial},server=on,wait=off',
                    '-serial',f'unix:{entropy},server=on,wait=off',
                    '-qmp',f'unix:{qmp},server=on,wait=off',
                    '-netdev',f'user,id=test,restrict=on,hostfwd=tcp:127.0.0.1:{port}-:22',
                    '-device','ne2k_isa,irq=12,netdev=test',
                    '-drive',f'file={disk},format=raw,if=ide','-boot','c'],stdout=log,stderr=log)
                deadline=time.monotonic()+10
                while not serial.exists() or not entropy.exists():
                    if proc.poll() is not None or time.monotonic()>deadline: raise RuntimeError('QEMU startup failed')
                    time.sleep(.05)
                provider=EntropyProvider(entropy,args.entropy);provider.start()
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.connect(str(serial));conn.settimeout(.2)
                    def receive(pattern,timeout=45):
                        data=bytearray();end=time.monotonic()+timeout
                        while time.monotonic()<end:
                            try: chunk=conn.recv(8192)
                            except socket.timeout: continue
                            if not chunk: raise RuntimeError('Serial disconnected')
                            data.extend(chunk);transcript.extend(chunk)
                            (out/'serial.txt').write_bytes(transcript)
                            if re.search(pattern,data):return bytes(data)
                        raise RuntimeError('Serial timeout: '+repr(pattern))
                    receive(rb'login:');conn.sendall(b'root\r');receive(rb'# ')
                    counter=0
                    def command(text,expected=0,timeout=45):
                        nonlocal counter
                        counter+=1;marker=('STEP%d='%counter).encode()
                        conn.sendall((text+'; echo STEP%d=$?\r'%counter).encode())
                        data=receive(rb'\r?\n'+marker+rb'(\d+)\r?\n',timeout)
                        if int(re.search(marker+rb'(\d+)\r?\n',data).group(1))!=expected:
                            raise RuntimeError('Command failed: '+text)
                        return data
                    command('uname -a')
                    if args.entropy!='healthy':
                        refusal=command('sshtest -F -r /etc/hostkey',expected=1,timeout=60)
                        if b'Failure reading random device' not in refusal:raise RuntimeError('Expected entropy refusal')
                        result['entropy_failure_closed']=True
                    else:
                        command('ktcp -b -p ne0 10.0.2.15 10.0.2.2 255.255.255.0')
                        command('sshtest -F -r /etc/hostkey -D /etc > /tmp/sshd.log 2>&1 &')
                        # The private host-forward only listens on loopback. Probe
                        # once with the actual authenticated client after startup.
                        time.sleep(2)
                        command('cat /tmp/sshd.log')
                        ssh=['ssh','-F','/dev/null','-vv','-p',str(port),'-i',str(temp/'clientkey'),
                             '-oBatchMode=yes','-oIdentitiesOnly=yes','-oIdentityAgent=none','-oStrictHostKeyChecking=yes',
                             '-oUserKnownHostsFile='+str(temp/'known_hosts'),'-oGlobalKnownHostsFile=/dev/null',
                             '-oConnectTimeout='+str(args.connect_timeout),'-oConnectionAttempts=1','-oPreferredAuthentications=publickey',
                             'root@127.0.0.1','echo ELKSSH_LOGIN_OK']
                        # Redirect output so no secret fixture paths or keys are
                        # printed in tool output. Logs get temp-path redaction.
                        try:
                            attempt=subprocess.run(ssh,capture_output=True,text=True,timeout=600)
                            sshlog=attempt.stderr.replace(str(temp),'$TEST')
                            (out/'ssh.txt').write_text(sshlog)
                            (out/'command.txt').write_text(attempt.stdout)
                            result['ssh_exit']=attempt.returncode
                            result['host_key_verified']='known and matches the ED25519 host key' in sshlog
                            result['newkeys_received']='SSH2_MSG_NEWKEYS received' in sshlog
                            result['encrypted_auth_service']='SSH2_MSG_SERVICE_ACCEPT received' in sshlog
                            result['publickey_login']=attempt.returncode==0 and 'ELKSSH_LOGIN_OK' in attempt.stdout
                        except subprocess.TimeoutExpired as exc:
                            result['ssh_timeout']=True
                            (out/'ssh.txt').write_text((exc.stderr or b'').decode(errors='replace').replace(str(temp),'$TEST'))
                        command('cat /tmp/sshd.log')
                        command('ps')
                    command('echo SHELL_STILL_WORKS')
                    if b'STACK USING' in transcript or b'STACK OVERFLOW' in transcript:
                        raise RuntimeError('Guest stack reservation exceeded')
                    if provider.error: raise RuntimeError(provider.error)
                    if provider.requests == 0: raise RuntimeError('Entropy transport was never exercised')
                    if args.screenshot:
                        command("echo -e '\\033[2J\\033[H' > /dev/tty1")
                        command('echo QEMU ONLY - HOST-FED ENTROPY > /dev/tty1')
                        command('cat /tmp/sshd.log > /dev/tty1')
                        with socket.socket(socket.AF_UNIX) as control:
                            control.connect(str(qmp))
                            stream=control.makefile('rwb');stream.readline()
                            for request in [{'execute':'qmp_capabilities'},
                                {'execute':'screendump','arguments':{'filename':str(out/'ssh.ppm')}}]:
                                stream.write((json.dumps(request)+'\n').encode());stream.flush()
                                while True:
                                    response=json.loads(stream.readline())
                                    if 'error' in response: raise RuntimeError(response)
                                    if 'return' in response: break
                    result['status']='passed' if args.entropy!='healthy' or result.get('publickey_login') else 'blocked'
        except Exception as exc:
            result['error']=str(exc)
        finally:
            if provider:
                provider.stop_event.set();provider.join(timeout=2)
                result['entropy_requests']=provider.requests
                result['entropy_bytes_sent']=provider.bytes_sent
                result['entropy_provider_error']=provider.error
            if proc and proc.poll() is None:
                proc.terminate();proc.wait(timeout=10)
            result['original_image_unchanged']=sha(args.image)==result['image_sha256']
            (out/'serial.txt').write_bytes(transcript)
            (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    return 0 if result['status']=='passed' and result['original_image_unchanged'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--image',type=Path,required=True)
    p.add_argument('--server',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cpu',choices=['486','pentium'],default='486')
    p.add_argument('--screenshot',action='store_true')
    p.add_argument('--connect-timeout',type=int,default=300)
    p.add_argument('--entropy',choices=['healthy','short','silent'],default='healthy')
    raise SystemExit(run(p.parse_args()))
