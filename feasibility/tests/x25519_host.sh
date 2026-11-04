#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p build/x25519-host
flags='-std=c99 -Os -Wall -Wextra -fwrapv -DBR_NO_ARITH_SHIFT=1 -fsanitize=address,undefined -fno-omit-frame-pointer'
for slow in 0 1; do
    cc $flags -DUSE_BEARSSL -DBR_SLOW_MUL15=$slow -DBACKEND_NAME=\"m15-$slow\" \
        -Ivendor/bearssl/inc -Ivendor/bearssl/src src/xbench.c \
        vendor/bearssl/src/ec/ec_c25519_m15.c vendor/bearssl/src/codec/ccopy.c \
        -o build/x25519-host/m15-$slow
    build/x25519-host/m15-$slow
done
cc $flags -Itests/shim -Ivendor/dropbear/src src/xbench.c \
    vendor/dropbear/src/curve25519.c -o build/x25519-host/baseline
build/x25519-host/baseline
python3 tests/provenance.py
