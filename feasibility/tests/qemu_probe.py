#!/usr/bin/env python3
"""MIT. Run probes in a disposable ELKS FAT image, without hardware access.

Requires QEMU and mtools. Host/guest networking is restricted; no port forwards.
QEMU CPU models do not emulate the original 8086/8088.
"""
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    baseline = sha(args.image)
    transcript = bytearray()
    result = {'cpu': args.cpu, 'status': 'failed', 'image_sha256': baseline,
              'cryptest_sha256': sha(args.build / 'cryptest'),
              'osprobe_sha256': sha(args.build / 'osprobe'),
              'qemu': subprocess.check_output(['qemu-system-i386', '--version'],
                                             text=True).splitlines()[0],
              'original_8086_execution': 'not tested'}
    if args.client:
        result['dbclient_sha256'] = sha(args.client)
    if args.wiretest:
        result['wiretest_sha256'] = sha(args.wiretest)
    if args.iotest:
        result['iotest_sha256'] = sha(args.iotest)
    if args.server:
        result['dropbear_sha256'] = sha(args.server)
    with tempfile.TemporaryDirectory(prefix='esh-') as directory:
        temp = Path(directory)
        disk = temp / 'disk.img'
        shutil.copyfile(args.image, disk)
        opts = subprocess.check_output(['mtype', '-i', str(disk), '::/bootopts'])
        opts += b'\nconsole=ttyS0,19200 3\n'
        if len(opts) > 1023:
            raise RuntimeError('bootopts exceeds ELKS limit')
        (temp / 'bootopts').write_bytes(opts)
        subprocess.run(['mcopy', '-o', '-i', str(disk), str(temp / 'bootopts'),
                        '::/bootopts'], check=True)
        for name in ('cryptest', 'osprobe'):
            subprocess.run(['mcopy', '-o', '-i', str(disk), str(args.build / name),
                            '::/bin/' + name], check=True)
        if args.client:
            subprocess.run(['mcopy', '-o', '-i', str(disk), str(args.client),
                            '::/bin/dbclient'], check=True)
        if args.wiretest:
            subprocess.run(['mcopy', '-o', '-i', str(disk), str(args.wiretest),
                            '::/bin/wiretest'], check=True)
        if args.iotest:
            subprocess.run(['mcopy', '-o', '-i', str(disk), str(args.iotest),
                            '::/bin/iotest'], check=True)
        if args.server:
            subprocess.run(['mcopy', '-o', '-i', str(disk), str(args.server),
                            '::/bin/dropbear'], check=True)
        serial, qmp = temp / 'serial', temp / 'qmp'
        with (out / 'qemu.log').open('w') as log:
            proc = subprocess.Popen([
                'qemu-system-i386', '-machine', 'pc', '-cpu', args.cpu,
                '-accel', 'tcg,one-insn-per-tb=on', '-m', '16M',
                '-display', 'none', '-monitor', 'none',
                '-serial', f'unix:{serial},server=on,wait=off',
                '-qmp', f'unix:{qmp},server=on,wait=off',
                '-netdev', 'user,id=probe,restrict=on',
                '-device', 'ne2k_isa,irq=12,netdev=probe',
                '-drive', f'file={disk},format=raw,if=ide', '-boot', 'c'],
                stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 10
                while not serial.exists():
                    if time.monotonic() > deadline or proc.poll() is not None:
                        raise RuntimeError('QEMU did not start')
                    time.sleep(.05)
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.connect(str(serial))
                    conn.settimeout(.2)

                    def receive(pattern, timeout=45):
                        collected = bytearray()
                        end = time.monotonic() + timeout
                        while time.monotonic() < end:
                            try:
                                chunk = conn.recv(8192)
                                if not chunk:
                                    raise RuntimeError('Serial disconnected')
                                collected.extend(chunk)
                                transcript.extend(chunk)
                            except socket.timeout:
                                continue
                            if re.search(pattern, collected):
                                return bytes(collected)
                        raise RuntimeError('Serial timeout: ' + repr(pattern))

                    receive(rb'login:')
                    conn.sendall(b'root\r')
                    receive(rb'# ')
                    counter = 0

                    def command(text, timeout=45, expected=0):
                        nonlocal counter
                        counter += 1
                        marker = 'PROBE%d' % counter
                        conn.sendall((text + '; echo ' + marker + '=$?\r').encode())
                        pattern = rb'\r?\n' + marker.encode() + rb'=(\d+)\r?\n'
                        data = receive(pattern, timeout)
                        if int(re.search(pattern, data).group(1)) != expected:
                            raise RuntimeError('Guest command failed: ' + text)
                        return data

                    result['uname'] = command('uname -a').decode('latin1')
                    down = command('osprobe')
                    if b'TCP socket: unavailable' not in down:
                        raise RuntimeError('Expected disconnected baseline')
                    if b'PTY: /dev/ptyp' not in down:
                        raise RuntimeError('PTY unavailable')
                    if b'Current account lookup: available' not in down:
                        raise RuntimeError('Account lookup unavailable')
                    if args.wiretest:
                        wire = command('wiretest')
                        if b'RESULT PASS checks=15 failures=0' not in wire or b'FAIL' in wire:
                            raise RuntimeError('Wire regression failed')
                        if b'STACK USING' in wire or b'STACK OVERFLOW' in wire:
                            raise RuntimeError('Wire regression exceeded reserved stack')
                        vectors = json.loads((Path(__file__).resolve().parents[2] /
                                              'tests/chachapoly-vectors.json').read_text())
                        for sequence, ciphertext in vectors.items():
                            if ('VECTOR ' + sequence + ' ' + ciphertext).encode() not in wire:
                                raise RuntimeError('Cipher reference mismatch: ' + sequence)
                        result['wire_regressions'] = 15
                        result['independent_cipher_vectors'] = 4
                    if args.iotest:
                        io = command('iotest')
                        if b'RESULT PASS I/O' not in io or b'FAIL' in io:
                            raise RuntimeError('Signed I/O regression failed')
                        if b'STACK USING' in io or b'STACK OVERFLOW' in io:
                            raise RuntimeError('I/O regression exceeded reserved stack')
                        result['io_regressions'] = 2
                        if b'PASS unsigned peer port 65535' not in io:
                            raise RuntimeError('Unsigned peer-port regression failed')
                        result['peer_port_regressions'] = 1
                    if args.client:
                        # This inherited client seeds before parsing even -V.
                        # Confirm an unavailable RNG cannot enter a connection.
                        refusal = command('dbclient -V', expected=1)
                        if b'Failure reading random device' not in refusal:
                            raise RuntimeError('Client did not fail for missing entropy')
                        if b'Weak entropy fallback' in refusal:
                            raise RuntimeError('Weak entropy fallback was used')
                        if b'STACK USING' in refusal or b'STACK OVERFLOW' in refusal:
                            raise RuntimeError('Client exceeded its stack reservation')
                        result['client_entropy_failure_closed'] = True
                    if args.server:
                        version = command('dropbear -V')
                        if b'Dropbear v2025.89' not in version:
                            raise RuntimeError('Unexpected server version output')
                        refusal = command('dropbear -F', expected=1)
                        if b'Failure reading random device' not in refusal:
                            raise RuntimeError('Server did not fail for missing entropy')
                        for text in (b'Weak entropy fallback', b'STACK USING', b'STACK OVERFLOW'):
                            if text in refusal or text in version:
                                raise RuntimeError('Unsafe server startup: ' + repr(text))
                        result['server_version_passed'] = True
                        result['server_entropy_failure_closed'] = True
                    start = time.monotonic()
                    crypto = command('cryptest', 300)
                    result['crypto_host_elapsed_seconds'] = round(time.monotonic()-start, 3)
                    if b'RESULT PASS failures=0' not in crypto or b'FAIL' in crypto:
                        raise RuntimeError('Crypto known-answer test failed')
                    if crypto.count(b'PASS ') != 11:
                        raise RuntimeError('Unexpected number of crypto passes')
                    if b'ABI int=2 long=4 pointer=2 longlong=8' not in crypto:
                        raise RuntimeError('Unexpected ELKS ABI')
                    command('ktcp -b -p ne0 10.0.2.15 10.0.2.2 255.255.255.0')
                    for attempt in range(3):
                        up = command('osprobe')
                        if b'TCP socket: allocated and closed' in up:
                            break
                        time.sleep(.3)
                    else:
                        raise RuntimeError('TCP socket unavailable after ktcp start')
                    command('net stop')
                    stopped = command('osprobe')
                    if b'TCP socket: unavailable' not in stopped:
                        raise RuntimeError('Expected stack-down state after stop')
                    command('echo SHELL_STILL_WORKS')
                    if args.screenshot:
                        command("echo -e '\\033[2J\\033[H' > /dev/tty1")
                        if args.server and args.wiretest:
                            command('wiretest | grep -v VECTOR > /dev/tty1')
                            command('dropbear -V > /dev/tty1 2>&1')
                            command('dropbear -F > /dev/tty1 2>&1', expected=1)
                        else:
                            command('cryptest > /dev/tty1', 300)
                    command('sync')
                with socket.socket(socket.AF_UNIX) as control:
                    control.connect(str(qmp))
                    stream = control.makefile('rwb')
                    stream.readline()

                    def qcommand(name, arguments=None):
                        stream.write((json.dumps({'execute': name,
                                      'arguments': arguments or {}}) + '\n').encode())
                        stream.flush()
                        while True:
                            response = json.loads(stream.readline())
                            if 'error' in response:
                                raise RuntimeError(response)
                            if 'return' in response:
                                return

                    qcommand('qmp_capabilities')
                    if args.screenshot:
                        filename = 'server.ppm' if args.server and args.wiretest else 'crypto.ppm'
                        qcommand('screendump', {'filename': str(out / filename)})
                    qcommand('quit')
                    proc.wait(timeout=10)
                result['status'] = 'passed'
                result['checks'] = ['10 crypto checks', '16-bit ABI', 'PTY allocation',
                                    'account lookup', 'TCP down/start/stop', 'shell survives']
            except Exception as exc:
                result['error'] = str(exc)
                raise
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)
                result['original_image_unchanged'] = sha(args.image) == baseline
                (out / 'serial.txt').write_bytes(transcript)
                (out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    if not result['original_image_unchanged']:
        raise RuntimeError('Original image changed')
    print('PASS QEMU ' + args.cpu + ': ' + str(out), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, required=True,
                        help='Unpartitioned bootable ELKS FAT image, stack stopped')
    parser.add_argument('--build', type=Path, default=Path('build'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cpu', choices=['486', 'pentium', 'qemu32'], default='486')
    parser.add_argument('--screenshot', action='store_true')
    parser.add_argument('--client', type=Path,
                        help='Optional dbclient built with weak entropy disabled')
    parser.add_argument('--wiretest', type=Path,
                        help='Optional production-code 16-bit wire regression executable')
    parser.add_argument('--server', type=Path,
                        help='Optional server version and no-entropy startup checks only')
    parser.add_argument('--iotest', type=Path,
                        help='Optional production atomicio signed-size regression')
    run(parser.parse_args())
