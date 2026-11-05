#!/usr/bin/env python3
"""MIT. Verify no-byte-output checker with public and temporary secret state."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from fixture import initial, record, generate
from provision import create_bundle, validate
from qemu_probe import boot, sha


def successor(state):
    value, k, v = generate(state[12:44], state[44:76])
    return value, record(k, v, int.from_bytes(state[8:12], 'big')+1)


def run(args, case):
    output = args.out/case
    result = dict(case=case, status='failed', secret_state_used=case=='secret-restart')
    with tempfile.TemporaryDirectory(prefix='esh-check-') as tmp:
        temp = Path(tmp); disk = temp/'disk.img'
        shutil.copyfile(args.image, disk)

        def mfs(*words, force=False):
            return subprocess.check_output([str(args.mfs), *(['-f'] if force else []),
                                            str(disk), *map(str, words)])

        opts = mfs('cat', '/bootopts')+b'\nconsole=ttyS0,19200 3\n'
        if len(opts)>1023: raise RuntimeError('Bootopts too long')
        (temp/'bootopts').write_bytes(opts); mfs('cp',temp/'bootopts','/bootopts')
        mfs('cp',args.check,'/bin/rngcheck'); mfs('mkdir','/root/rngtest')
        if case == 'secret-restart':
            create_bundle(temp/'private', args.helper)
            state = (temp/'private/state').read_bytes()
            validate(state)
        else:
            state = record(*initial())
        if case == 'checksum':
            state = state[:20]+bytes([state[20]^1])+state[21:]
        source = temp/'state'; source.write_bytes(state); source.chmod(0o600)
        mfs('cp',source,'/root/rngtest/state')
        setup=['chmod 700 /bin/rngcheck','chmod 700 /root/rngtest']
        if case=='busy': setup.append('echo busy > /root/rngtest/lock')
        if case=='missing': setup.append('rm /root/rngtest/state')
        command = 'rngcheck unexpected' if case=='arguments' else 'rngcheck'
        rounds=2 if case=='secret-restart' else 1
        result['rounds']=[]
        for index in range(rounds):
            stage=output/str(index+1)
            check=boot(disk,stage,setup if index==0 else [],command)
            transcript=(stage/'serial.txt').read_bytes()
            if check['outputs'] or b'PUBLIC-FIXTURE' in transcript or b'STAGE ' in transcript:
                raise RuntimeError('Checker exposed diagnostic bytes/stages; keep logs private')
            if case in ('healthy','secret-restart'):
                discarded, advanced=successor(state)
                if discarded.hex().encode() in transcript:
                    raise RuntimeError('Generated output leaked; keep logs private')
                if (check['exit_code']!=0
                        or b'\nRNGCHECK OK: request consumed; output discarded\r\n' not in transcript
                        or mfs('cat','/root/rngtest/state',force=True)!=advanced):
                    raise RuntimeError('Successful consumption/state check failed')
                state=advanced
            elif case=='arguments':
                if check['exit_code']!=2 or mfs('cat','/root/rngtest/state',force=True)!=state:
                    raise RuntimeError('Invalid arguments consumed state')
            else:
                if check['exit_code']!=1 or b'\nRNGCHECK REFUSED\r\n' not in transcript:
                    raise RuntimeError('Bad source was not refused')
                if case!='missing' and mfs('cat','/root/rngtest/state',force=True)!=state:
                    raise RuntimeError('Refusal altered state')
            # No seed, state, secret fingerprint, or discarded output in report.
            result['rounds'].append(dict(exit_code=check['exit_code'],state_check_passed=True,
                                         no_generated_output=True))
        result['status']='passed'
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('image','mfs','check','helper','out'):
        parser.add_argument('--'+name,required=True,type=lambda s:Path(s).resolve())
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    initial_hash=sha(args.image)
    summary=dict(status='failed',image_sha256=initial_hash,check_sha256=sha(args.check),
                 cpu='486',disk_cache='writethrough',cases=[])
    try:
        for case in ('healthy','arguments','busy','missing','checksum','secret-restart'):
            summary['cases'].append(run(args,case))
        summary['status']='passed'
    except Exception:
        # Avoid exceptions containing secret record values. Failed logs are
        # not publication evidence and require inspection before sharing.
        summary['error']='Check failed; inspect private local logs before publication'
    finally:
        summary['original_image_unchanged']=sha(args.image)==initial_hash
        if not summary['original_image_unchanged']:summary['status']='failed'
        (args.out/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    raise SystemExit(summary['status']!='passed')
