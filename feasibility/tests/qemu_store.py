#!/usr/bin/env python3
"""MIT. Test write/sync/readback with public patterns in disposable MINIX images.

QEMU blkdebug faults target only the preallocated pattern block. VM termination
is not a physical power cut. This does not establish a secure RNG lifecycle.
"""
import argparse
import errno
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(args, case):
    output = args.out / case
    output.mkdir(parents=True, exist_ok=True)
    transcript = bytearray()
    result = dict(case=case, status='failed', physical_power_loss=False)
    with tempfile.TemporaryDirectory(prefix='esh-store-') as directory:
        temp = Path(directory)
        disk = temp / 'disk.img'
        shutil.copyfile(args.image, disk)

        def mfs(*words):
            return subprocess.check_output([str(args.mfs), str(disk), *map(str, words)])

        opts = mfs('cat', '/bootopts') + b'\nconsole=ttyS0,19200 3\n'
        if len(opts) > 1023:
            raise RuntimeError('bootopts too long')
        (temp/'bootopts').write_bytes(opts)
        mfs('cp', temp/'bootopts', '/bootopts')
        mfs('cp', args.probe, '/bin/storeprobe')
        (temp/'pattern').write_bytes(b'A'*1024)
        mfs('cp', temp/'pattern', '/root/store.dat')
        image = disk.read_bytes()
        offset = image.find(b'A'*1024)
        if offset < 0 or offset % 1024 or image.find(b'A'*1024, offset+1) >= 0:
            raise RuntimeError('Pattern must occupy one unique aligned MINIX block')
        result['pattern_sector'] = offset//512
        source = str(disk)
        if case.startswith(('eio-', 'enospc-')):
            sector = offset//512 + int(case.rsplit('-', 1)[1])
            code = errno.EIO if case.startswith('eio-') else errno.ENOSPC
            config = ('[inject-error]\nevent = "write_aio"\niotype = "write"\n'
                      'errno = "%d"\nsector = "%d"\n' % (code, sector))
            (temp/'fault.conf').write_text(config)
            (output/'fault.conf').write_text(config)
            source = 'blkdebug:%s:%s' % (temp/'fault.conf', disk)
        serial = temp/'serial'
        with (output/'qemu.log').open('w') as log:
            proc = subprocess.Popen([
                'qemu-system-i386', '-machine', 'pc', '-cpu', '486',
                '-accel', 'tcg,one-insn-per-tb=on', '-m', '16M',
                '-display', 'none', '-monitor', 'none', '-nic', 'none',
                '-serial', 'unix:%s,server=on,wait=off' % serial,
                '-drive', 'file=%s,format=raw,if=ide,cache=writethrough,werror=report,rerror=report' % source,
                '-boot', 'c'], stdout=log, stderr=log)
            try:
                end = time.monotonic()+10
                while not serial.exists():
                    if time.monotonic() > end or proc.poll() is not None:
                        raise RuntimeError('QEMU failed to start')
                    time.sleep(.05)
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.connect(str(serial))
                    conn.settimeout(.2)

                    def receive(pattern, timeout=60):
                        data = bytearray()
                        end = time.monotonic()+timeout
                        while time.monotonic() < end:
                            try:
                                chunk = conn.recv(8192)
                            except socket.timeout:
                                continue
                            if not chunk:
                                raise RuntimeError('Guest disconnected')
                            data.extend(chunk)
                            transcript.extend(chunk)
                            (output/'serial.txt').write_bytes(transcript)
                            if re.search(pattern, data):
                                return bytes(data)
                        raise RuntimeError('Guest timed out')

                    receive(rb'login:')
                    conn.sendall(b'root\r')
                    receive(rb'# ')
                    conn.sendall(b'chmod 700 /bin/storeprobe\r')
                    receive(rb'# ')
                    pause = int(case[-1]) if case.startswith('crash-') else 0
                    command = 'storeprobe /root/store.dat %d; echo STORE=$?\r' % pause
                    conn.sendall(command.encode())
                    if pause:
                        data = receive(('STAGE %d\r?\n' % pause).encode())
                        result['stopped_at_stage'] = pause
                    else:
                        data = receive(rb'\r?\nSTORE=(\d+)\r?\n')
                        result['exit_code'] = int(re.search(rb'\r?\nSTORE=(\d+)', data)[1])
                    result['guest_acknowledged'] = b'ACKNOWLEDGED update' in data
                    result['guest_refused'] = b'REFUSED ' in data
            except Exception as exc:
                result['error'] = str(exc)
            finally:
                # No guest shutdown/sync: observe the bytes already written.
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=10)
        actual = disk.read_bytes()[offset:offset+1024]
        result['disk_record'] = 'old' if actual == b'A'*1024 else 'new' if actual == b'B'*1024 else 'mixed'
        if 'error' not in result:
            if case == 'healthy':
                passed = result['guest_acknowledged'] and result['exit_code'] == 0 and result['disk_record'] == 'new'
            elif case.startswith('crash-'):
                passed = not result['guest_acknowledged']
                if pause == 1:
                    passed &= result['disk_record'] == 'old'
                elif pause >= 3:
                    passed &= result['disk_record'] == 'new'
            else:
                passed = result['guest_refused'] and result['exit_code'] != 0 and result['disk_record'] != 'new'
            result['status'] = 'passed' if passed else 'failed'
    (output/'serial.txt').write_bytes(transcript)
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ['image', 'mfs', 'probe', 'out']:
        p.add_argument('--'+name, type=lambda s: Path(s).resolve(), required=True)
    cases = ['healthy','eio-0','eio-1','enospc-0','enospc-1','crash-1','crash-2','crash-3','crash-4']
    p.add_argument('--cases', nargs='+', choices=cases, default=cases)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    original = sha(a.image)
    report = dict(image_sha256=original, probe_sha256=sha(a.probe),
                  qemu=subprocess.check_output(['qemu-system-i386','--version'], text=True).splitlines()[0],
                  disk_cache='writethrough', cpu='486', cases=[])
    try:
        for case in a.cases:
            result = run_case(a, case)
            report['cases'].append(result)
            print(json.dumps(result), flush=True)
    finally:
        report['original_image_unchanged'] = sha(a.image) == original
        report['status'] = 'passed' if (report['original_image_unchanged'] and len(report['cases']) == len(a.cases)
                              and all(c['status']=='passed' for c in report['cases'])) else 'failed'
        (a.out/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(0 if report['status'] == 'passed' else 1)
