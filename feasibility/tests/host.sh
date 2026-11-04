#!/bin/sh
# MIT. Run the same public vectors on the host, plus provenance and ISA tests.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
mkdir -p build/host
${CC:-cc} -std=c99 -Os -Wall -Wextra -fwrapv \
    -Itests/shim -Ivendor/dropbear/src -Ivendor/tinyssh -Ivendor/tinyssh/cryptoint \
    src/cryptest.c vendor/dropbear/src/curve25519.c \
    vendor/tinyssh/crypto_hash_sha256.c vendor/tinyssh/crypto_stream_chacha20.c \
    -o build/host/cryptest
build/host/cryptest
python3 tests/provenance.py
python3 -m unittest discover -s tools -p 'test_*.py'
