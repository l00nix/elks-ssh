#!/usr/bin/env python3
"""Regression checks against a retained medium-model ELKS daemon build."""
import argparse
import importlib.util
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location('isa_audit', Path(__file__).resolve().parents[1] / 'tools/isa-audit.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
p = argparse.ArgumentParser()
p.add_argument('executable', type=Path)
p.add_argument('elf', type=Path)
p.add_argument('disassembly', type=Path)
p.add_argument('link_map', type=Path)
a = p.parse_args()

def check(path):
    return audit_module.audit(path, a.elf, a.disassembly, a.link_map)

original = a.executable.read_bytes()
report = check(a.executable)
assert report['isa_static_pass'], report['ambiguities']
assert report['memory']['far_text_bytes'] > 0
print('PASS exact near/far code matches and passes ISA audit')
with tempfile.TemporaryDirectory(prefix='elkssh-audit-') as directory:
    candidate = Path(directory) / 'candidate'
    corrupt = bytearray(original)
    corrupt[report['memory']['header_bytes']] ^= 1
    candidate.write_bytes(corrupt)
    assert not check(candidate)['isa_static_pass']
    print('PASS changed near-code byte rejected')
    offset = report['memory']['header_bytes'] + report['memory']['text_bytes']
    corrupt = bytearray(original)
    corrupt[offset] ^= 1
    candidate.write_bytes(corrupt)
    result = check(candidate)
    assert not result['isa_static_pass']
    assert any('.fartext differs' in x['reason'] for x in result['ambiguities'])
    print('PASS changed far-code byte rejected despite unchanged ELF/disassembly')
    corrupt = bytearray(original)
    struct.pack_into('<I', corrupt, 48, 0)
    candidate.write_bytes(corrupt)
    assert not check(candidate)['isa_static_pass']
    print('PASS missing far-code header length rejected')
    candidate.write_bytes(original[:offset+10])
    assert not check(candidate)['isa_static_pass']
    print('PASS truncated far-code payload rejected')
    candidate.write_bytes(original[:40])
    try:
        check(candidate)
    except ValueError as error:
        assert 'supplemental header' in str(error)
    else:
        raise AssertionError('Truncated supplemental header accepted')
    print('PASS truncated supplemental header rejected')
