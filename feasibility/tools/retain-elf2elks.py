#!/usr/bin/env python3
"""MIT. Retain pre-conversion linked code for auditing exact executable bytes."""
import os
from pathlib import Path
import shutil
import sys

for argument in sys.argv[1:]:
    candidate = Path(argument)
    if candidate.is_file():
        with candidate.open('rb') as stream:
            if stream.read(4) == b'\x7fELF':
                shutil.copyfile(candidate, str(candidate) + '.elf')
                break
converter = os.environ['ELKSSH_REAL_ELF2ELKS']
os.execv(converter, [converter] + sys.argv[1:])
