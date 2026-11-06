#!/usr/bin/env python3
"""MIT. Disposable QEMU SSH test with isolated randomness and ephemeral keys.
Never runs on physical serial ports. Requires cryptography, QEMU and mtools.
No private keys, entropy bytes or reusable guest image are retained in outputs.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import importlib.util
import json
import os
import pty
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import termios
import tempfile
import threading
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from kex_rejection import reject_public_point


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EntropyProvider(threading.Thread):
    def __init__(self, path, mode, short_bytes=16, framed=None):
        super().__init__(daemon=True)
        self.path, self.mode = path, mode
        self.short_bytes = short_bytes
        self.stop_event = threading.Event()
        self.requests = 0
        self.bytes_sent = 0
        self.error = None
        self.framed = framed

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
                    size = 24 if self.framed else 2
                    while len(pending) >= size:
                        request = bytes(pending[:size]); del pending[:size]
                        if not self.framed and request != bytes([2,32]):
                            raise RuntimeError('Unexpected entropy request framing')
                        self.requests += 1
                        if self.mode == 'silent': continue
                        fresh = self.framed.answer(request) if self.framed else os.urandom(32)
                        if self.mode == 'short': fresh = fresh[:self.short_bytes]
                        conn.sendall(fresh)
                        self.bytes_sent += len(fresh)
        except Exception as exc:
            if not self.stop_event.is_set(): self.error = str(exc)


def run(args):
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    persistent = args.persistent_entropy
    failure_mode = args.entropy != 'healthy' or args.persistent_fault != 'none'
    result = {'status':'failed', 'entropy_mode':args.entropy,
              'entropy_protocol':'persistent-state' if persistent else ('serial-framed' if args.serial_entropy else 'qemu-egd'),
              'server_sha256':sha(args.server), 'image_sha256':sha(args.image),
              'filesystem':args.filesystem, 'cpu':args.cpu, 'real_hardware':False, 'production_entropy':False,
              'ssh_client':subprocess.run(['ssh','-V'],capture_output=True,text=True).stderr.strip()}
    transcript = bytearray()
    with tempfile.TemporaryDirectory(prefix='esh-ssh-') as directory:
        temp = Path(directory)
        disk = temp/'disk.img'; shutil.copyfile(args.image,disk)
        def put(source, target):
            if args.filesystem == 'minix':
                subprocess.run([str(args.mfs),str(disk),'cp',str(source),target],check=True)
            else:
                subprocess.run(['mcopy','-o','-i',str(disk),str(source),'::'+target],check=True)
        opts = subprocess.check_output([str(args.mfs),str(disk),'cat','/bootopts']
            if args.filesystem == 'minix' else ['mtype','-i',str(disk),'::/bootopts'])
        opts += b'\nconsole=ttyS0,19200 3\n'
        assert len(opts)<=1023
        (temp/'bootopts').write_bytes(opts); put(temp/'bootopts','/bootopts')
        shutil.copyfile(args.server,temp/'sshtest');os.chmod(temp/'sshtest',0o700)
        put(temp/'sshtest','/bin/sshtest')
        if args.inetd_launcher:
            shutil.copyfile(args.inetd_launcher,temp/'sshlisten')
            os.chmod(temp/'sshlisten',0o700)
            put(temp/'sshlisten','/bin/sshlisten')
            result['inetd_launcher_sha256']=sha(args.inetd_launcher)
            result['connection_model']='single-worker inetd experiment'
        authdir = '/root' if args.filesystem == 'minix' else '/etc'
        framed = None
        initial_persistent_state = None
        if persistent:
            source=Path(__file__).resolve().parents[1]/'experimental/persistent-entropy/provision.py'
            spec=importlib.util.spec_from_file_location('persistent_provision',source)
            provision=importlib.util.module_from_spec(spec);spec.loader.exec_module(provision)
            provision.create_bundle(temp/'private-rng',args.seed_helper)
            initial_persistent_state=(temp/'private-rng/state').read_bytes()
            subprocess.run([str(args.mfs),str(disk),'mkdir','/root/rngtest'],check=True)
            if args.persistent_fault=='checksum':
                initial_persistent_state=initial_persistent_state[:20]+bytes([initial_persistent_state[20]^1])+initial_persistent_state[21:]
                (temp/'private-rng/state').write_bytes(initial_persistent_state)
            if args.persistent_fault!='missing':
                put(temp/'private-rng/state','/root/rngtest/state')
            if args.persistent_fault=='busy':
                (temp/'private-rng/lock').touch(mode=0o600)
                put(temp/'private-rng/lock','/root/rngtest/lock')
            if failure_mode:
                # A readable deterministic fallback must not bypass source failure.
                (temp/'fake-random').write_bytes(b'not-valid-entropy'.ljust(32,b'!'))
                put(temp/'fake-random','/dev/urandom')
            result['persistent_fault']=args.persistent_fault
        if args.serial_entropy:
            source=Path(__file__).resolve().parents[1]/'experimental/serial-entropy/provider.py'
            spec=importlib.util.spec_from_file_location('serial_entropy_provider',source)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            framed=module.Provider();framed.bootstrap(temp/'entropy-bootstrap')
            subprocess.run([str(args.mfs),str(disk),'mkdir','/root/ssh1105'],check=True)
            for name in ['esession','ecounter']:
                put(temp/'entropy-bootstrap'/name,'/root/ssh1105/'+name)
        # Dropbear's private Ed25519 format: SSH string algorithm, then
        # a 64-byte string containing the fresh seed followed by its public key.
        host = Ed25519PrivateKey.generate()
        seed = host.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
        public = host.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        def string(value): return struct.pack('>I',len(value))+value
        (temp/'hostkey').write_bytes(string(b'ssh-ed25519')+string(seed+public))
        os.chmod(temp/'hostkey',0o600); put(temp/'hostkey',authdir+'/hostkey')
        client = Ed25519PrivateKey.generate()
        (temp/'clientkey').write_bytes(client.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.OpenSSH,serialization.NoEncryption()))
        os.chmod(temp/'clientkey',0o600)
        clientpub=client.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)
        (temp/'authorized_keys').write_bytes(clientpub+b' test-only\n')
        os.chmod(temp/'authorized_keys',0o600)
        put(temp/'authorized_keys',authdir+'/authkeys')
        payload=('0123456789abcdef'*63+'\n')*16
        (temp/'payload').write_text(payload);os.chmod(temp/'payload',0o600)
        if args.filesystem=='minix': put(temp/'payload','/root/payload')
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
                    *([] if persistent else ['-serial',f'unix:{entropy},server=on,wait=off']),
                    '-qmp',f'unix:{qmp},server=on,wait=off',
                    '-netdev',f'user,id=test,restrict=on,hostfwd=tcp:127.0.0.1:{port}-:22',
                    '-device','ne2k_isa,irq=12,netdev=test',
                    '-drive',f'file={disk},format=raw,if=ide'+(',cache=writethrough,werror=report,rerror=report' if persistent else ''),'-boot','c'],stdout=log,stderr=log)
                deadline=time.monotonic()+10
                while not serial.exists() or (not persistent and not entropy.exists()):
                    if proc.poll() is not None or time.monotonic()>deadline: raise RuntimeError('QEMU startup failed')
                    time.sleep(.05)
                if not persistent:
                    provider=EntropyProvider(entropy,args.entropy,args.entropy_bytes,framed);provider.start()
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
                    if persistent:
                        command('chmod 700 /root/rngtest')
                    if args.serial_entropy:
                        command('chmod 600 /dev/ttyS1')
                        command('chmod 700 /root/ssh1105')
                        command('chmod 600 /root/ssh1105/esession /root/ssh1105/ecounter')
                    if failure_mode:
                        refusal=command('sshtest -F -r '+authdir+'/hostkey',expected=1,timeout=60)
                        refusal_text=b'Failure reading persistent random state' if persistent else b'Failure reading random device'
                        if refusal_text not in refusal:raise RuntimeError('Expected entropy refusal')
                        result['entropy_failure_closed']=True
                        state=command('ps')
                        if any(b'sshtest ' in row for row in state.splitlines()
                               if re.match(rb'\s*\d+\s',row)):
                            raise RuntimeError('Server remained after entropy refusal')
                        result['entropy_failure_no_server_process']=True
                    else:
                        command('ktcp -b -p ne0 10.0.2.15 10.0.2.2 255.255.255.0')
                        command('ls -ld / /root '+authdir+'/authkeys')
                        service=('sshlisten 22 /bin/sshtest -i' if args.inetd_launcher else 'sshtest -F')
                        command(service+' -r '+authdir+'/hostkey -D '+authdir+' > /tmp/sshd.log 2>&1 &')
                        # The private host-forward only listens on loopback. Probe
                        # once with the actual authenticated client after startup.
                        time.sleep(2)
                        command('cat /tmp/sshd.log')
                        if args.kex_rejection_suite:
                            result['kex_rejections'] = {}
                            for label, point in [('zero', bytes(32)), ('one', b'\x01'+bytes(31)),
                                                 ('short', bytes(31))]:
                                before = command('cat /tmp/sshd.log').count(b'Bad curve25519')
                                rejection = reject_public_point(port, point)
                                after = command('cat /tmp/sshd.log').count(b'Bad curve25519')
                                if not rejection['closed'] or rejection['reached_newkeys'] or after != before+1:
                                    raise RuntimeError('Expected specific X25519 rejection: '+label)
                                rejection['specific_server_rejection'] = True
                                for _ in range(10):
                                    state = command('ps').decode('latin1')
                                    active = [line for line in state.splitlines()
                                              if re.match(r'\s*\d+\s',line) and 'sshtest ' in line]
                                    if len(active) == 1: break
                                    time.sleep(1)
                                if len(active) != 1:
                                    raise RuntimeError('KEX rejection child was not reaped: '+label)
                                rejection['connection_child_reaped'] = True
                                result['kex_rejections'][label] = rejection
                        ssh=['ssh','-F','/dev/null','-vv','-p',str(port),'-i',str(temp/'clientkey'),
                             '-oBatchMode=yes','-oIdentitiesOnly=yes','-oIdentityAgent=none','-oStrictHostKeyChecking=yes',
                             '-oUserKnownHostsFile='+str(temp/'known_hosts'),'-oGlobalKnownHostsFile=/dev/null',
                             '-oConnectTimeout='+str(args.connect_timeout),'-oConnectionAttempts=1','-oPreferredAuthentications=publickey',
                             'root@127.0.0.1','echo ELKSSH_LOGIN_OK; ps; sleep 5']
                        if args.suite:
                            # Hold one unauthenticated connection. The second
                            # must close without a banner, preserving the slot.
                            with socket.create_connection(('127.0.0.1',port),timeout=10) as held:
                                held.settimeout(20)
                                banner=held.recv(512)
                                if not banner.startswith(b'SSH-2.0-'): raise RuntimeError('Held connection has no SSH banner')
                                with socket.create_connection(('127.0.0.1',port),timeout=10) as excess:
                                    excess.settimeout(10)
                                    try: reply=excess.recv(512)
                                    except ConnectionResetError: reply=b''
                                    result['preauth_limit']=reply==b''
                                    if reply: raise RuntimeError('Unauthenticated slot released prematurely')
                            for _ in range(10):
                                state=command('ps').decode('latin1')
                                active=[line for line in state.splitlines() if re.match(r'\s*\d+\s',line) and 'sshtest ' in line]
                                if len(active)==1: break
                                time.sleep(1)
                            if len(active)!=1: raise RuntimeError('Held connection child was not reaped')
                        snapshots=[]
                        cases={}
                        def attempt_case(name, argv, expected_exit=0, expected_output=None, rejection=None,
                                         input_text='', output_patterns=(), require_pty=False, require_rekey=False,
                                         terminal_eof=False):
                            start=time.monotonic()
                            timed_out=False
                            stdout_path=temp/(name+'.stdout');stderr_path=temp/(name+'.stderr')
                            input_path=temp/(name+'.stdin');input_path.write_text(input_text)
                            with ExitStack() as resources:
                                stdout=resources.enter_context(stdout_path.open('w'))
                                stderr=resources.enter_context(stderr_path.open('w'))
                                stdin=resources.enter_context(input_path.open('rb'))
                                client_env=None
                                if require_pty and not terminal_eof:
                                    # Model a live 80x24 terminal. The separate
                                    # terminal_eof case sends immediate SSH EOF.
                                    master,slave=pty.openpty()
                                    resources.callback(os.close,master)
                                    resources.callback(os.close,slave)
                                    fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
                                    stdin=slave
                                    client_env=dict(os.environ,TERM='vt100')
                                attempt=subprocess.Popen(argv,stdin=stdin,stdout=stdout,stderr=stderr,env=client_env)
                                try:
                                    while attempt.poll() is None:
                                        if time.monotonic()-start>600:
                                            timed_out=True
                                            break
                                        if not args.no_memory_sampling:
                                            snapshots.append({'case':name,'host_elapsed_seconds':round(time.monotonic()-start,3),
                                                              'ps':command('ps').decode('latin1')})
                                        time.sleep(2)
                                finally:
                                    if attempt.poll() is None: attempt.kill();attempt.wait()
                                    (out/'memory.json').write_text(json.dumps(snapshots,indent=2)+'\n')
                            sshlog=stderr_path.read_text().replace(str(temp),'$TEST')
                            sshstdout=stdout_path.read_text()
                            (out/('ssh-'+name+'.txt')).write_text(sshlog)
                            (out/('command-'+name+'.txt')).write_text(sshstdout)
                            authenticated='using "publickey"' in sshlog and 'Authenticated to ' in sshlog
                            case={'ssh_exit':attempt.returncode,'timeout':timed_out,
                                  'host_key_verified':'known and matches the ED25519 host key' in sshlog,
                                  'newkeys_received':'SSH2_MSG_NEWKEYS received' in sshlog,
                                  'encrypted_auth_service':'SSH2_MSG_SERVICE_ACCEPT received' in sshlog,
                                  'authenticated':authenticated,
                                  'host_elapsed_seconds':round(time.monotonic()-start,3)}
                            case['passed']=(not timed_out and attempt.returncode==expected_exit
                                and (expected_output is None or sshstdout==expected_output)
                                and (rejection is None or (rejection in sshlog and not authenticated)))
                            if expected_exit != 255: case['passed'] &= authenticated and case['host_key_verified']
                            if output_patterns:
                                case['output_patterns_matched']=all(re.search(pattern,sshstdout,re.M) for pattern in output_patterns)
                                case['passed'] &= case['output_patterns_matched']
                            if require_pty:
                                case['pty_accepted']='PTY allocation request accepted' in sshlog
                                case['passed'] &= case['pty_accepted']
                            if require_rekey:
                                case['newkeys_received_count']=sshlog.count('SSH2_MSG_NEWKEYS received')
                                case['passed'] &= case['newkeys_received_count']>=2
                            cases[name]=case
                            result['cases']=cases
                            # Verify that the connection child was reaped, including
                            # negative tests that close during key exchange.
                            for _ in range(5):
                                state=command('ps').decode('latin1')
                                server_rows=[line for line in state.splitlines() if re.match(r'\s*\d+\s',line) and 'sshtest ' in line]
                                if len(server_rows)==1: break
                                time.sleep(1)
                            case['connection_child_reaped']=len(server_rows)==1
                            case['passed'] &= case['connection_child_reaped']
                            command('cat /tmp/sshd.log')
                            return case
                        # Delayed output catches premature EOF on a temporarily
                        # empty pipe. Compare the entire stdout, not just a marker.
                        ssh[-1]='echo ELKSSH_LOGIN_OK; sleep 2; echo ELKSSH_DONE'
                        first=attempt_case('login',ssh,expected_output='ELKSSH_LOGIN_OK\nELKSSH_DONE\n')
                        result.update({key:first[key] for key in ['ssh_exit','host_key_verified','newkeys_received','encrypted_auth_service']})
                        result['publickey_login']=first['passed']
                        if args.suite and first['passed']:
                            wrong=Ed25519PrivateKey.generate()
                            (temp/'wrongkey').write_bytes(wrong.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.OpenSSH,serialization.NoEncryption()))
                            os.chmod(temp/'wrongkey',0o600)
                            badkey=ssh.copy();badkey[badkey.index('-i')+1]=str(temp/'wrongkey')
                            attempt_case('wrong-key',badkey,expected_exit=255,rejection='Permission denied (publickey)')
                            badhost=Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)
                            (temp/'wrong_hosts').write_bytes(('[127.0.0.1]:%d '%port).encode()+badhost+b'\n')
                            badpin=[('-oUserKnownHostsFile='+str(temp/'wrong_hosts')) if a.startswith('-oUserKnownHostsFile=') else a for a in ssh]
                            attempt_case('wrong-host',badpin,expected_exit=255,rejection='Host key verification failed')
                            for name,target,unsafe,safe in [('unsafe-dir',authdir,'777','700'),('unsafe-key',authdir+'/authkeys','666','600')]:
                                command('chmod '+unsafe+' '+target)
                                try: attempt_case(name,ssh,expected_exit=255,rejection='Permission denied (publickey)')
                                finally: command('chmod '+safe+' '+target)
                            stream=ssh.copy();stream[-1]='cat /root/payload; sleep 2; echo STREAM_DONE'
                            attempt_case('stream',stream,expected_output=payload+'STREAM_DONE\n')
                            repeat=ssh.copy();repeat[-1]='echo ELKSSH_REPEAT_OK; exit 7'
                            attempt_case('repeat-exit',repeat,expected_exit=7,expected_output='ELKSSH_REPEAT_OK\n')
                        if args.session_suite and first['passed']:
                            input_case=ssh.copy();input_case[-1]='cat; echo INPUT_EOF_OK'
                            text_input='ELKSSH_STDIN\nsecond line\n'
                            attempt_case('stdin-eof',input_case,input_text=text_input,
                                expected_output=text_input+'INPUT_EOF_OK\n')
                            pty_case=ssh.copy();pty_case.insert(1,'-tt')
                            pty_case[-1]='echo PTY_BEGIN; tty; ps; cat /etc/issue; echo PTY_DONE'
                            attempt_case('pty-commands',pty_case,require_pty=True,
                                output_patterns=(r'^PTY_BEGIN$',r'^/dev/tty',r'PID.*COMMAND',r'ELKS 0\.9\.2',r'^PTY_DONE$'))
                            attempt_case('pty-input-eof',pty_case,require_pty=True,terminal_eof=True,
                                output_patterns=(r'^PTY_BEGIN$',r'^/dev/tty',r'PID.*COMMAND',r'ELKS 0\.9\.2',r'^PTY_DONE$'))
                            rekey=ssh.copy();rekey.insert(1,'-oRekeyLimit=4K')
                            rekey[-1]='cat /root/payload; echo REKEY_DONE'
                            attempt_case('rekey-output',rekey,expected_output=payload+'REKEY_DONE\n',require_rekey=True)
                        result['suite_passed']=all(case['passed'] for case in cases.values()) and result.get('preauth_limit',True)
                        result['memory_sampling_enabled']=not args.no_memory_sampling
                        rows=[]
                        for sample in snapshots:
                            for line in sample['ps'].splitlines():
                                if re.match(r'\s*\d+\s',line):
                                    worker=re.search(r'\s(\d+)\s+(\d+)\s+(\d+)\s+(?:/bin/)?sshtest ',line)
                                    if worker: rows.append(tuple(map(int,worker.groups())))
                        if rows:
                            result['sampled_memory']={'samples':len(snapshots),'max_heap_brk_bytes':max(r[0] for r in rows),
                                'min_sp_minus_brk_bytes':min(r[1] for r in rows),'process_size_bytes':sorted(set(r[2] for r in rows)),
                                'peak_bound':False}
                    if args.listener_stop_test:
                        if not args.inetd_launcher or failure_mode:
                            raise RuntimeError('Listener stop test requires a healthy inetd launcher')
                        with socket.create_connection(('127.0.0.1',port),timeout=10) as held:
                            held.settimeout(20)
                            if not held.recv(512).startswith(b'SSH-2.0-'):
                                raise RuntimeError('Stop-test worker has no SSH banner')
                            state=command('ps').decode('latin1')
                            parents=[line.split()[0] for line in state.splitlines()
                                     if re.match(r'\s*\d+\s',line) and 'sshlisten 22 ' in line]
                            if len(parents)!=1: raise RuntimeError('Expected one listener to stop')
                            stopping_ids={line.split()[0] for line in state.splitlines()
                                          if re.match(r'\s*\d+\s',line) and 'sshtest ' in line}
                            command('kill '+parents[0])
                            for _ in range(10):
                                state=command('ps').decode('latin1')
                                remaining=[line for line in state.splitlines()
                                           if re.match(r'\s*\d+\s',line) and line.split()[0] in stopping_ids]
                                if not remaining: break
                                time.sleep(1)
                            # Drain an already queued KEXINIT before checking EOF.
                            closed=False
                            deadline=time.monotonic()+20
                            while time.monotonic()<deadline:
                                held.settimeout(max(.1,deadline-time.monotonic()))
                                try:
                                    if not held.recv(4096): closed=True; break
                                except ConnectionResetError: closed=True; break
                                except socket.timeout: break
                            result['listener_stop_reaps_worker']=not remaining and closed
                            if not result['listener_stop_reaps_worker']:
                                raise RuntimeError('Listener stop left a worker or connection')
                    command('echo SHELL_STILL_WORKS')
                    if b'STACK USING' in transcript or b'STACK OVERFLOW' in transcript:
                        raise RuntimeError('Guest stack reservation exceeded')
                    if provider and provider.error: raise RuntimeError(provider.error)
                    if provider and provider.requests == 0: raise RuntimeError('Entropy transport was never exercised')
                    if args.screenshot:
                        command("echo -e '\\033[2J\\033[H' > /dev/tty1")
                        command('echo QEMU ONLY - '+('PERSISTENT STATE' if persistent else 'HOST-FED ENTROPY')+' > /dev/tty1')
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
                    result['status']='passed' if failure_mode or (result.get('publickey_login') and result.get('suite_passed')) else 'blocked'
        except Exception as exc:
            result['error']=str(exc)
        finally:
            if provider:
                provider.stop_event.set();provider.join(timeout=2)
                result['entropy_requests']=provider.requests
                result['entropy_bytes_sent']=provider.bytes_sent
                result['entropy_provider_error']=provider.error
                if args.entropy == 'short':
                    result['entropy_response_bytes']=args.entropy_bytes
                    if provider.requests == 0 or provider.bytes_sent != provider.requests*args.entropy_bytes:
                        result['status']='failed'
                        result['error']='Short entropy responses were not exercised as requested'
                if provider.error:
                    result['status']='failed'
                    result['error']='Entropy provider failed unexpectedly'
            if proc and proc.poll() is None:
                proc.terminate();proc.wait(timeout=10)
            if persistent:
                result['runtime_entropy_helper']=False
                # Inspect only after QEMU stops. Never include state/seed values
                # or their fingerprints in the report or exception text.
                saved=subprocess.run([str(args.mfs),'-f',str(disk),'cat','/root/rngtest/state'],capture_output=True)
                valid=False
                if args.persistent_fault=='missing':
                    valid=saved.returncode!=0
                elif failure_mode:
                    valid=saved.returncode==0 and saved.stdout==initial_persistent_state
                elif saved.returncode==0 and len(saved.stdout)==1024:
                    generation=int.from_bytes(saved.stdout[8:12],'big')
                    if (1 if args.inetd_launcher else 2)<=generation<=1024:
                        source=Path(__file__).resolve().parents[1]/'experimental/persistent-entropy/fixture.py'
                        spec=importlib.util.spec_from_file_location('private_state_reference',source)
                        reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
                        k,v=initial_persistent_state[12:44],initial_persistent_state[44:76]
                        for _ in range(generation):discard,k,v=reference.generate(k,v)
                        valid=saved.stdout==reference.record(k,v,generation)
                        result['persistent_generation']=generation
                result['persistent_state_check_passed']=valid
                if not valid:
                    result['status']='failed';result['error']='Persistent state did not match expected lifecycle'
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
    p.add_argument('--filesystem',choices=['fat','minix'],default='fat')
    p.add_argument('--mfs',type=lambda s:Path(s).resolve())
    p.add_argument('--cpu',choices=['486','pentium'],default='486')
    p.add_argument('--suite',action='store_true',help='Also test rejected keys/permissions, host mismatch and repeated login')
    p.add_argument('--session-suite',action='store_true',help='Also test stdin EOF, PTY commands and forced rekeying')
    p.add_argument('--kex-rejection-suite',action='store_true',help='Reject public low-order and short X25519 inputs before login')
    p.add_argument('--screenshot',action='store_true')
    p.add_argument('--connect-timeout',type=int,default=300)
    p.add_argument('--no-memory-sampling',action='store_true',help='Do not launch ps during SSH cases; compare failures without monitor memory pressure')
    p.add_argument('--inetd-launcher',type=lambda s:Path(s).resolve(),help='Isolated single-worker launcher for Dropbear -i memory comparison')
    p.add_argument('--listener-stop-test',action='store_true',help='Stop the experimental listener with a connected pre-auth worker and verify cleanup')
    p.add_argument('--entropy',choices=['healthy','short','silent'],default='healthy')
    p.add_argument('--serial-entropy',action='store_true',help='Use the isolated framed serial adapter through a private QEMU socket')
    p.add_argument('--persistent-entropy',action='store_true',help='Use fresh offline-provisioned state without a runtime entropy helper')
    p.add_argument('--seed-helper',type=lambda s:Path(s).resolve(),help='Trusted locally built seed-record helper')
    p.add_argument('--persistent-fault',choices=['none','missing','busy','checksum'],default='none')
    p.add_argument('--entropy-bytes',type=int,choices=range(32),default=16,
                   help='Bytes per short entropy response (0 through 31; default 16)')
    args=p.parse_args()
    if args.filesystem=='minix' and args.mfs is None: p.error('--mfs is required for MINIX')
    if args.persistent_entropy and (args.serial_entropy or args.filesystem!='minix' or args.entropy!='healthy' or args.seed_helper is None):
        p.error('--persistent-entropy requires MINIX, healthy mode, --seed-helper and no serial adapter')
    if args.persistent_fault!='none' and (not args.persistent_entropy or args.suite or args.session_suite or args.kex_rejection_suite or args.screenshot):
        p.error('--persistent-fault requires standalone persistent-source testing without suites/screenshots')
    if args.serial_entropy and (args.filesystem!='minix' or args.entropy!='healthy'):
        p.error('--serial-entropy requires MINIX and healthy input; use the serial probe matrix for fault cases')
    if (args.suite or args.session_suite) and (args.filesystem!='minix' or args.entropy!='healthy'):
        p.error('Suites require --filesystem minix and healthy entropy')
    if args.kex_rejection_suite and args.entropy!='healthy':
        p.error('KEX rejection suite requires healthy test entropy')
    if args.screenshot and args.entropy!='healthy':
        p.error('--screenshot requires healthy entropy')
    raise SystemExit(run(args))
