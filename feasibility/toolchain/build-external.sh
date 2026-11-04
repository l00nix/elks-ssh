#!/bin/sh
# MIT. Build probes with the prepared ELKS toolchain; no kernel modifications.
set -eu
TOPDIR=${ELKSSH_ELKS:-${TOPDIR:-}}
: "${TOPDIR:?Set TOPDIR or ELKSSH_ELKS to a prepared ELKS checkout}"
TOPDIR=$(CDPATH= cd -- "$TOPDIR" && pwd)
export TOPDIR
PATH="$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
export PATH
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
mkdir -p build
rm -f build/cryptest build/osprobe
if [ "${ELKSSH_AUDIT:-0}" = 1 ]; then
    # Optional development-only dependency; not required by the minimal build.
    mkdir -p build/host-tools
    cp tools/retain-elf2elks.py build/host-tools/elf2elks
    chmod +x build/host-tools/elf2elks
    ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
    export ELKSSH_REAL_ELF2ELKS
    PATH="$PWD/build/host-tools:$PATH"
    export PATH
fi
# -fwrapv matches the signed-arithmetic requirements of the imported crypto.
set -- -march=i8086 -mtune=i8086 -mcmodel=small -melks-libc \
    -mno-segment-relocation-stuff -Os -Wall -Wextra -fwrapv \
    -fstack-usage -fno-builtin-printf -fno-builtin-fprintf \
    -I"$TOPDIR/include" -I"$TOPDIR/libc/include" -I"$TOPDIR/elks/include"
ia16-elf-gcc "$@" -Itests/shim -Ivendor/dropbear/src \
    -Ivendor/tinyssh -Ivendor/tinyssh/cryptoint \
    -maout-heap=1024 -maout-stack=8192 -Wl,-Map,build/cryptest.map \
    src/cryptest.c vendor/dropbear/src/curve25519.c \
    vendor/tinyssh/crypto_hash_sha256.c vendor/tinyssh/crypto_stream_chacha20.c \
    -o build/cryptest
ia16-elf-gcc "$@" -maout-heap=2048 -maout-stack=2048 \
    -Wl,-Map,build/osprobe.map src/osprobe.c -o build/osprobe
printf '%s\n' 'Built feasibility probes only: build/cryptest build/osprobe'
