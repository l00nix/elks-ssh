#!/usr/bin/env python3
"""MIT. Offline recovery experiment with PUBLIC input only; not an installer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from fixture import update, generate, record
from provision import validate
from qemu_probe import boot, sha


def oracle(seed, count):
    k, v = update(bytes(32), b'\1'*32, seed)
    outputs = []
    for _ in range(count):
        value, k, v = generate(k, v)
        outputs.append(value.hex())
    return outputs, record(k, v, count)


def run(args):
    before = sha(args.image)
    result = dict(status='failed', public_test_data_only=True, hardware=False,
                  image_sha256=before, probe_sha256=sha(args.probe),
                  helper_sha256=sha(args.helper), cpu='486', disk_cache='writethrough')
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='esh-recover-') as tmp:
            temp = Path(tmp); disk = temp/'disk.img'
            shutil.copyfile(args.image, disk)

            def mfs(*words, force=False):
                return subprocess.check_output([str(args.mfs), *(['-f'] if force else []),
                                                str(disk), *map(str, words)])

            def flush():
                with disk.open('r+b') as f:
                    os.fsync(f.fileno())

            def make_state(seed):
                proc = subprocess.run([str(args.helper)], input=seed,
                                      capture_output=True, check=True)
                validate(proc.stdout)
                assert proc.stdout == oracle(seed, 0)[1] and not proc.stderr
                state = temp/'state'; state.write_bytes(proc.stdout); state.chmod(0o600)
                return state

            seed_a, seed_b = bytes(range(48)), bytes(reversed(range(48)))
            opts = mfs('cat', '/bootopts') + b'\nconsole=ttyS0,19200 3\n'
            assert len(opts) <= 1023
            (temp/'bootopts').write_bytes(opts)
            mfs('cp', temp/'bootopts', '/bootopts')
            mfs('cp', args.probe, '/bin/persistprobe')
            mfs('mkdir', '/root/rngtest')
            mfs('cp', make_state(seed_a), '/root/rngtest/state')
            setup = ['chmod 700 /bin/persistprobe', 'chmod 700 /root/rngtest',
                     'chmod 600 /root/rngtest/state']
            first = boot(disk, args.out/'initial', setup, 'persistprobe')
            assert first['outputs'] == oracle(seed_a, 1)[0] and first['exit_code'] == 0
            result['initial'] = first
            stopped = boot(disk, args.out/'interrupted', [], 'persistprobe 3', pause=3)
            assert not stopped['outputs']
            refused = boot(disk, args.out/'refused', [], 'persistprobe')
            assert refused['refused'] and refused['exit_code'] == 1 and not refused['outputs']
            result['interrupted_refused'] = refused
            # QEMU has exited. Recovery never edits the image of a running VM.
            # This -f applies only to this killed disposable fixture, not to
            # arbitrary corrupt real media or a production fsck replacement.
            old = mfs('cat', '/root/rngtest/state', force=True)
            mfs('cat', '/root/rngtest/lock', force=True)
            fresh = make_state(seed_b).read_bytes()
            assert old != fresh
            mfs('cp', temp/'state', '/root/rngtest/state', force=True)
            flush()
            assert mfs('cat', '/root/rngtest/state', force=True) == fresh
            mfs('rm', '/root/rngtest/lock', force=True)
            flush()
            recovered = boot(disk, args.out/'recovered', [], 'persistprobe')
            assert recovered['exit_code'] == 0 and recovered['outputs'] == oracle(seed_b, 1)[0]
            assert mfs('cat', '/root/rngtest/state', force=True) == oracle(seed_b, 1)[1]
            result['recovered'] = recovered
            restarted = boot(disk, args.out/'recovery-restart', [], 'persistprobe')
            assert restarted['exit_code'] == 0 and restarted['outputs'] == oracle(seed_b, 2)[0][-1:]
            assert mfs('cat', '/root/rngtest/state', force=True) == oracle(seed_b, 2)[1]
            result.update(recovery_restart=restarted, fresh_state_matches_reference=True,
                          old_sequence_not_resumed=True, status='passed')
    except Exception as exc:
        result['error'] = repr(exc)  # Only public fixture data in this harness.
    finally:
        result['original_image_unchanged'] = sha(args.image) == before
        if not result['original_image_unchanged']:
            result['status'] = 'failed'
        (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'mfs', 'probe', 'helper', 'out'):
        parser.add_argument('--'+name, required=True, type=lambda s: Path(s).resolve())
    outcome = run(parser.parse_args())
    print(json.dumps(outcome, indent=2))
    raise SystemExit(outcome['status'] != 'passed')
