#!/usr/bin/env python3
"""Compare public X25519 vectors in a disposable ELKS FAT fixture; no network."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time

p = argparse.ArgumentParser()
p.add_argument('--image', type=Path, required=True)
p.add_argument('--build', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--quick', action='store_true', help='One identical vector per backend')
a = p.parse_args()
a.names = ['xbase', 'xm15-0', 'xm15-1']
a.out.mkdir(parents=True, exist_ok=True)
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
original = sha(a.image)
result = {'status': 'failed', 'cpu': '486', 'image_sha256': original,
          'real_hardware': False, 'production_crypto_selected': False, 'cases': {}}
transcript = bytearray()
try:
    with tempfile.TemporaryDirectory(prefix='esh-xbench-') as directory:
        temp = Path(directory)
        disk = temp/'disk.img'
        shutil.copyfile(a.image, disk)
        opts = subprocess.check_output(['mtype', '-i', str(disk), '::/bootopts'])
        opts += b'\nconsole=ttyS0,19200 3\n'
        assert len(opts) <= 1023
        (temp/'bootopts').write_bytes(opts)
        subprocess.run(['mcopy', '-o', '-i', str(disk), str(temp/'bootopts'), '::/bootopts'], check=True)
        for name in a.names:
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,14}', name):
                raise ValueError('Probe name must be a short basename')
            result[name+'_sha256'] = sha(a.build/name)
            subprocess.run(['mcopy', '-o', '-i', str(disk), str(a.build/name), '::/bin/'+name], check=True)
        serial = temp/'serial'
        with (a.out/'qemu.log').open('w') as log:
            proc = subprocess.Popen(['qemu-system-i386', '-machine', 'pc', '-cpu', '486',
                '-accel', 'tcg,one-insn-per-tb=on', '-m', '16M', '-display', 'none',
                '-monitor', 'none', '-nic', 'none',
                '-serial', f'unix:{serial},server=on,wait=off',
                '-drive', f'file={disk},format=raw,if=ide', '-boot', 'c'], stdout=log, stderr=log)
            try:
                end = time.monotonic()+10
                while not serial.exists():
                    if time.monotonic()>end or proc.poll() is not None:
                        raise RuntimeError('QEMU failed to start')
                    time.sleep(.05)
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.connect(str(serial)); conn.settimeout(.2)
                    def receive(pattern):
                        data = bytearray(); end = time.monotonic()+900
                        while time.monotonic()<end:
                            try:
                                chunk = conn.recv(8192)
                            except socket.timeout:
                                continue
                            if not chunk: raise RuntimeError('Serial disconnected')
                            data.extend(chunk); transcript.extend(chunk)
                            (a.out/'serial.txt').write_bytes(transcript)
                            if re.search(pattern, data): return bytes(data)
                        raise RuntimeError('Guest response timed out')
                    receive(rb'login:'); conn.sendall(b'root\r'); receive(rb'# ')
                    for i, name in enumerate(a.names):
                        marker = 'XBENCH%d' % i
                        quick = a.quick or name == 'xbase'
                        count = 1 if quick else 12
                        command = name + (' quick' if quick else '')
                        began = time.monotonic()
                        conn.sendall((command+'; echo '+marker+'=$?\r').encode())
                        pattern = rb'\r?\n'+marker.encode()+rb'=(\d+)\r?\n'
                        data = receive(pattern)
                        expected = ('RESULT PASS checks=%d failures=0' % count).encode()
                        passed = (expected in data and int(re.search(pattern,data)[1]) == 0
                                  and b'FAIL' not in data and b'STACK' not in data)
                        timings = re.findall(rb'PASS ([a-z0-9-]+) seconds=(\d+)',data)
                        passed = passed and len(timings) == count
                        result['cases'][name] = dict(passed=passed, checks=count,
                            host_seconds=round(time.monotonic()-began,3),
                            vector_seconds={n.decode():int(t) for n,t in timings})
                        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
                        if not passed: raise RuntimeError(name+' failed')
                    result['status'] = 'passed'
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait()
except Exception as error:
    result['error'] = str(error)
finally:
    result['original_image_unchanged'] = sha(a.image) == original
    if not result['original_image_unchanged']: result['status'] = 'failed'
    (a.out/'serial.txt').write_bytes(transcript)
    (a.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['status']=='passed' else 1)
