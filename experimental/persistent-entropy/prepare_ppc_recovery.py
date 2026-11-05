#!/usr/bin/env python3
"""MIT. Prepare a PUBLIC-fixture PPC recovery image, never secret provisioning.

Requires the known interrupted generation-three fixture and audited probe.
Preserves the input, checks unmounted filesystems, and boots only scratch copies.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from fixture import expected
from qemu_probe import boot, sha
from qemu_recovery import oracle
from provision import validate

PROBE_SHA = 'fd1134ac2356102187ede2f1f9d1e818c945424c85ed96d75a0c93f69e40edb2'
PUBLIC_SEED = bytes(reversed(range(48)))
MARKER = b'PPC recovery test: PUBLIC fixture, not SSH entropy.\nSeed: bytes 47 down to 0. Initial generation: 0.\n'


def run(args):
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    original = sha(args.image)
    checker_original = sha(args.checker)
    result = dict(status='failed', source_sha256=original,
                  source_bytes=args.image.stat().st_size,
                  checker_sha256=checker_original, public_test_data_only=True,
                  ssh_ready=False, cpu='486', disk_cache='writethrough')
    try:
        with tempfile.TemporaryDirectory(prefix='esh-ppc-recovery-') as tmp:
            temp = Path(tmp)

            def mfs(disk, *words, force=False):
                return subprocess.check_output([str(args.mfs), *(['-f'] if force else []),
                                                str(disk), *map(str, words)])

            def flush(disk):
                with disk.open('r+b') as f:
                    os.fsync(f.fileno())

            def for_qemu(disk):
                # Only scratch boot copies: preserve hardware network/console
                # settings byte-for-byte in the deliverable.
                opts = mfs(disk, 'cat', '/bootopts', force=True)
                opts = re.sub(rb'^net=ne0$', b'#net=ne0', opts, flags=re.M)
                opts += b'\nconsole=ttyS0,19200 3\n'
                if len(opts) > 1023:
                    raise RuntimeError('QEMU bootopts exceeds limit')
                (temp/'bootopts').write_bytes(opts)
                mfs(disk, 'cp', temp/'bootopts', '/bootopts', force=True)

            def fsck(disk, name):
                checker = temp/(name+'-root.img')
                shutil.copyfile(args.checker, checker)
                for_qemu(checker)
                before = sha(disk)
                checked = boot(checker, args.out/name, [], 'fsck -fv /dev/hdb', secondary_disk=disk)
                checked['unmounted_target_unchanged'] = sha(disk) == before
                if checked['exit_code'] != 0 or not checked['unmounted_target_unchanged']:
                    raise RuntimeError('Filesystem check failed: '+name)
                return checked

            disk = temp/'hardware.img'
            shutil.copyfile(args.image, disk)
            result['source_fsck'] = fsck(disk, 'source-fsck')
            bootopts = mfs(disk, 'cat', '/bootopts')
            if mfs(disk, 'cat', '/root/rngtest/state') != expected(3)[1]:
                raise RuntimeError('Input is not the expected public interrupted state')
            if mfs(disk, 'cat', '/root/rngtest/lock') != b'':
                raise RuntimeError('Expected empty interrupted-operation lock')
            import hashlib
            if hashlib.sha256(mfs(disk, 'cat', '/root/rngtest/rngprobe')).hexdigest() != PROBE_SHA:
                raise RuntimeError('Unexpected probe binary')
            metadata = mfs(disk, 'ls', '-ld', '/root/rngtest', '/root/rngtest/state').decode()
            for mode, path in [('drwx------', '/root/rngtest'), ('-rw-------', '/root/rngtest/state')]:
                pattern = r'^'+re.escape(mode)+r'\s+\d+\s+\d+\s+0,\s+0\s+\d+[^\n]* '+re.escape(path)+r'$'
                if not re.search(pattern, metadata, re.M):
                    raise RuntimeError('Unexpected fixture ownership/mode')

            scratch = temp/'unrecovered.img'
            shutil.copyfile(disk, scratch); for_qemu(scratch)
            refused = boot(scratch, args.out/'unrecovered', [], '/root/rngtest/rngprobe')
            if not refused['refused'] or refused['exit_code'] != 1 or refused['outputs']:
                raise RuntimeError('Original interrupted state did not refuse')
            result['unrecovered'] = refused

            generated = subprocess.run([str(args.helper)], input=PUBLIC_SEED,
                                       capture_output=True, check=True)
            validate(generated.stdout)
            if generated.stderr or generated.stdout != oracle(PUBLIC_SEED, 0)[1]:
                raise RuntimeError('Public initializer does not match independent reference')
            state = temp/'state'; state.write_bytes(generated.stdout); state.chmod(0o600)
            # Offline ordering: replace, flush, read back, then clear old lock.
            mfs(disk, 'cp', state, '/root/rngtest/state'); flush(disk)
            if mfs(disk, 'cat', '/root/rngtest/state') != generated.stdout:
                raise RuntimeError('Replacement state failed readback')
            mfs(disk, 'rm', '/root/rngtest/lock'); flush(disk)
            marker = temp/'RECOVERY'; marker.write_bytes(MARKER); marker.chmod(0o600)
            mfs(disk, 'cp', marker, '/root/rngtest/RECOVERY'); flush(disk)
            if mfs(disk, 'cat', '/bootopts') != bootopts:
                raise RuntimeError('Hardware boot configuration changed')
            result['recovered_fsck'] = fsck(disk, 'recovered-fsck')

            verification = temp/'verification.img'
            shutil.copyfile(disk, verification); for_qemu(verification)
            for count, name in [(1, 'first-boot'), (2, 'restart')]:
                check = boot(verification, args.out/name, [], '/root/rngtest/rngprobe')
                outputs, final = oracle(PUBLIC_SEED, count)
                if (check['exit_code'] != 0 or check['outputs'] != outputs[-1:]
                        or check['failed_assertion']
                        or mfs(verification, 'cat', '/root/rngtest/state', force=True) != final):
                    raise RuntimeError('Recovery output/state failed: '+name)
                result[name] = check

            # Verify the physical artifact has never been booted or consumed.
            if mfs(disk, 'cat', '/root/rngtest/state') != oracle(PUBLIC_SEED, 0)[1]:
                raise RuntimeError('Hardware state was consumed during verification')
            prepared = args.out/'sshrec.img'
            with prepared.open('xb') as target, disk.open('rb') as source:
                os.chmod(prepared, 0o600)
                shutil.copyfileobj(source, target)
                target.flush(); os.fsync(target.fileno())
            if sha(prepared) != sha(disk):
                raise RuntimeError('Final image copy differs')
            result.update(status='passed', output_image='sshrec.img', output_sha256=sha(prepared),
                          output_bytes=prepared.stat().st_size, hardware_generation=0,
                          hardware_bootopts_preserved=True, probe_sha256=PROBE_SHA,
                          expected_first_public_output=oracle(PUBLIC_SEED, 1)[0][0],
                          expected_second_public_output=oracle(PUBLIC_SEED, 2)[0][1])
    except Exception as exc:
        result['error'] = repr(exc)  # Public fixtures only in this tool.
    finally:
        result['source_unchanged'] = sha(args.image) == original
        result['checker_unchanged'] = sha(args.checker) == checker_original
        if not result['source_unchanged'] or not result['checker_unchanged']:
            result['status'] = 'failed'
        (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'checker', 'mfs', 'helper', 'out'):
        parser.add_argument('--'+name, required=True, type=lambda s: Path(s).resolve())
    outcome = run(parser.parse_args())
    print(json.dumps(outcome, indent=2))
    raise SystemExit(outcome['status'] != 'passed')
