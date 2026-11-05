#!/usr/bin/env python3
"""MIT. Public-fixture persistent RNG tests; no SSH or physical device access."""
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
from fixture import initial, record, expected


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def boot(disk, output, setup, command, pause=0, source=None, secondary_disk=None):
    output.mkdir(parents=True, exist_ok=True)
    transcript = bytearray()
    with tempfile.TemporaryDirectory(prefix='esh-rng-') as directory:
        serial = Path(directory)/'serial'
        with (output/'qemu.log').open('w') as log:
            proc = subprocess.Popen([
                'qemu-system-i386', '-machine', 'pc', '-cpu', '486',
                '-accel', 'tcg,one-insn-per-tb=on', '-m', '16M',
                '-display', 'none', '-monitor', 'none', '-nic', 'none',
                '-serial', 'unix:%s,server=on,wait=off' % serial,
                '-drive', 'file=%s,format=raw,if=ide,cache=writethrough,werror=report,rerror=report' % (source or disk),
                '-boot', 'c',
                *(['-drive', 'file=%s,format=raw,if=ide,index=1,cache=writethrough' % secondary_disk]
                  if secondary_disk is not None else [])], stdout=log, stderr=log)
            try:
                end = time.monotonic()+10
                while not serial.exists():
                    if time.monotonic() > end or proc.poll() is not None:
                        raise RuntimeError('QEMU failed to start')
                    time.sleep(.05)
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.connect(str(serial)); conn.settimeout(.2)

                    def receive(pattern, timeout=60):
                        data = bytearray(); end = time.monotonic()+timeout
                        while time.monotonic() < end:
                            try: chunk = conn.recv(8192)
                            except socket.timeout: continue
                            if not chunk: raise RuntimeError('Guest disconnected')
                            data.extend(chunk); transcript.extend(chunk)
                            (output/'serial.txt').write_bytes(transcript)
                            if re.search(pattern, data): return bytes(data)
                        raise RuntimeError('Guest timed out')

                    receive(rb'login:'); conn.sendall(b'root\r'); receive(rb'# ')
                    for item in setup:
                        conn.sendall((item+'; echo SETUP=$?\r').encode())
                        reply = receive(rb'\r?\nSETUP=(\d+)\r?\n',180 if item.startswith('dd ') else 60)
                        expected_code = 1 if item.startswith('dd ') else 0
                        if int(re.search(rb'\r?\nSETUP=(\d+)', reply)[1]) != expected_code:
                            raise RuntimeError('Setup failed: '+item)
                        if item.startswith('dd ') and b'No space' not in reply:
                            raise RuntimeError('Filesystem full was not demonstrated')
                    conn.sendall((command+'; echo PROBE=$?\r').encode())
                    if pause:
                        data = receive(('STAGE %d\r?\n' % pause).encode())
                    else:
                        data = receive(rb'\r?\nPROBE=(\d+)\r?\n')
                    return dict(outputs=[v.decode() for v in re.findall(rb'PUBLIC-FIXTURE ([a-f0-9]{64})', data)],
                                refused=b'REFUSED output unchanged; process retry refused' in data,
                                exit_code=None if pause else int(re.search(rb'\r?\nPROBE=(\d+)', data)[1]),
                                stopped_at=pause or None,
                                contention_refused=b'PASS competing child refused while parent holds lock' in data,
                                failed_assertion=b'FAIL ' in data)
            finally:
                if proc.poll() is None: proc.kill()
                proc.wait(timeout=10)
                (output/'serial.txt').write_bytes(transcript)


def run(args, case):
    output = args.out/case; output.mkdir(parents=True, exist_ok=True)
    result = dict(case=case, status='failed', hardware=False, secrets_used=False)
    with tempfile.TemporaryDirectory(prefix='esh-persist-') as directory:
        temp = Path(directory); disk = temp/'disk.img'; shutil.copyfile(args.image, disk)

        def mfs(*words, force=False):
            return subprocess.check_output([str(args.mfs), *(['-f'] if force else []), str(disk), *map(str, words)])

        opts = mfs('cat','/bootopts')+b'\nconsole=ttyS0,19200 3\n'
        if len(opts)>1023: raise RuntimeError('bootopts too long')
        (temp/'bootopts').write_bytes(opts); mfs('cp',temp/'bootopts','/bootopts')
        mfs('cp',args.probe,'/bin/persistprobe'); mfs('mkdir','/root/rngtest')
        initial_record = record(*initial())
        fixture = initial_record
        if case == 'checksum': fixture = fixture[:13]+bytes([fixture[13]^1])+fixture[14:]
        if case == 'truncated': fixture = fixture[:-1]
        if case == 'exhausted': fixture = record(*initial(), count=1048576)
        (temp/'state').write_bytes(fixture); mfs('cp',temp/'state','/root/rngtest/state')
        setup = ['chmod 700 /bin/persistprobe','chmod 700 /root/rngtest','chmod 600 /root/rngtest/state']
        extras = {
            'bad-mode': ['chmod 644 /root/rngtest/state'],
            'bad-dir': ['chmod 755 /root/rngtest'],
            'missing': ['rm /root/rngtest/state'],
            'busy': ['echo busy > /root/rngtest/lock'],
            'hardlink': ['ln /root/rngtest/state /root/rngtest/alias'],
            'symlink': ['mv /root/rngtest/state /root/rngtest/orig','ln -s orig /root/rngtest/state'],
            'full-fs': ['dd if=/dev/zero of=/root/rngtest/fill bs=1024 count=32000'],
        }
        setup += extras.get(case, [])
        source = None
        if case.startswith(('eio-', 'enospc-')):
            image = disk.read_bytes(); offset = image.find(initial_record)
            if offset<0 or offset%1024 or image.find(initial_record, offset+1)>=0:
                raise RuntimeError('State must occupy a unique aligned block')
            code = errno.EIO if case.startswith('eio-') else errno.ENOSPC
            sector = offset//512+int(case[-1])
            config = ('[inject-error]\nevent = "write_aio"\niotype = "write"\n'
                      'errno = "%d"\nsector = "%d"\n' % (code, sector))
            (temp/'fault.conf').write_text(config); (output/'fault.conf').write_text(config)
            source = 'blkdebug:%s:%s' % (temp/'fault.conf', disk)
        pause = int(case[-1]) if case.startswith('crash-') else 0
        command = 'persistprobe '+case if case in ['fork','contend'] else 'persistprobe %d' % pause
        try:
            first = boot(disk,output/'first',setup,command,pause,source)
            result['first'] = first
            if case in ['healthy','fork','contend','full-fs']:
                n = 3 if case == 'fork' else 1
                outputs, state = expected(n)
                assert first['outputs']==outputs and first['exit_code']==0 and not first['failed_assertion']
                if case == 'contend': assert first['contention_refused']
                assert mfs('cat','/root/rngtest/state',force=True)==state
                second = boot(disk,output/'restart',[],'persistprobe')
                result['restart'] = second
                outputs, state = expected(n+1)
                assert second['outputs']==outputs[-1:] and second['exit_code']==0 and not second['failed_assertion']
                assert mfs('cat','/root/rngtest/state',force=True)==state
                result['state_matches_reference']=True
            elif pause:
                assert not first['outputs'] and not first['failed_assertion']
                second = boot(disk,output/'restart',[],'persistprobe')
                result['restart'] = second
                if pause < 6:
                    assert second['refused'] and second['exit_code']==1 and not second['outputs']
                    result['abandoned_lock_refused']=True
                else:
                    outputs, state = expected(2)
                    assert second['outputs']==outputs[-1:] and second['exit_code']==0
                    assert mfs('cat','/root/rngtest/state',force=True)==state
                    result['unexposed_output_skipped']=True
            else:
                assert first['refused'] and first['exit_code']==1 and not first['outputs'] and not first['failed_assertion']
                # Removing injected errors must not silently recover an abandoned lock.
                if case.startswith(('eio-','enospc-')):
                    second=boot(disk,output/'restart',[],'persistprobe')
                    result['restart']=second
                    assert second['refused'] and second['exit_code']==1 and not second['outputs']
            result['status']='passed'
        except Exception as exc:
            result['error']=repr(exc)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for name in ['image','mfs','probe','out']:
        p.add_argument('--'+name,type=lambda s:Path(s).resolve(),required=True)
    cases=['healthy','fork','contend','full-fs','bad-mode','bad-dir','missing','busy','hardlink','symlink','checksum','truncated','exhausted',
           'eio-0','eio-1','enospc-0','enospc-1',*['crash-%d'%n for n in range(1,7)]]
    p.add_argument('--cases',nargs='+',choices=cases,default=cases)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    before=sha(a.image)
    summary=dict(image_sha256=before,probe_sha256=sha(a.probe),cpu='486',disk_cache='writethrough',cases=[])
    try:
        for case in a.cases:
            result=run(a,case); summary['cases'].append(result); print(json.dumps(result),flush=True)
    finally:
        summary['original_image_unchanged']=sha(a.image)==before
        summary['status']='passed' if (summary['original_image_unchanged'] and len(summary['cases'])==len(a.cases)
                                 and all(c['status']=='passed' for c in summary['cases'])) else 'failed'
        (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    raise SystemExit(0 if summary['status']=='passed' else 1)
