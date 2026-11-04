#!/usr/bin/env python3
"""Fail if vendored source differs from its recorded upstream bytes."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1] / 'vendor'
count = 0
for project, details in json.loads((root / 'manifest.json').read_text()).items():
    for name, expected in details['files'].items():
        actual = hashlib.sha256((root / project / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit('Vendor mismatch: ' + project + '/' + name)
        count += 1
print('PASS unchanged vendor files:', count)
