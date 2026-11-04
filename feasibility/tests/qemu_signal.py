#!/usr/bin/env python3
"""Run signal-registration probes in a disposable ELKS FAT fixture."""
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
p.add_argument('--names', nargs='+', default=['sig-small', 'sig-medium'])
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
original = sha(a.image)
result = {'status': 'failed', 'cpu': '486', 'image_sha256': original,
          'real_hardware': False, 'signal_delivery_tested': False}
transcript = bytearray()
try:
    with tempfile.TemporaryDirectory(prefix='esh-sig-') as directory:
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
                        data = bytearray(); end = time.monotonic()+60
                        while time.monotonic()<end:
                            try:
                                chunk = conn.recv(8192)
                            except socket.timeout:
                                continue
                            if not chunk: raise RuntimeError('Serial disconnected')
                            data.extend(chunk); transcript.extend(chunk)
                            if re.search(pattern, data): return bytes(data)
                        raise RuntimeError('Guest response timed out')
                    receive(rb'login:'); conn.sendall(b'root\r'); receive(rb'# ')
                    for i, name in enumerate(a.names):
                        marker = 'SIGNAL%d' % i
                        conn.sendall((name+'; echo '+marker+'=$?\r').encode())
                        data = receive(rb'\r?\n'+marker.encode()+rb'=(\d+)\r?\n')
                        passed = b'RESULT failures=0' in data and marker.encode()+b'=0' in data
                        if name == 'sig-life':
                            passed = passed and b'delivered=8 child_notifications=8 reaped=8' in data
                            result['signal_delivery_tested'] = passed
                        result[name] = passed
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
