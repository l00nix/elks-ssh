#!/bin/sh
# MIT. No-byte-output consumer of the experimental persistent adapter.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to a prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out=${ELKSSH_CHECK_OUT:-"$root/build/rngcheck"}
mkdir -p "$out/audit-tools"
out=$(CDPATH= cd -- "$out" && pwd)
cp "$root/tools/retain-elf2elks.py" "$out/audit-tools/elf2elks"
chmod +x "$out/audit-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$out/audit-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$out"
br="$root/vendor/bearssl"
ia16-elf-gcc -mcmodel=medium -melks-libc -march=i8086 -mtune=i8086 \
    -Os -Wall -Wextra -Werror -fstack-usage -DBR_NO_ARITH_SHIFT=1 \
    -maout-heap=1024 -maout-stack=8192 -I"$br/inc" -I"$br/src" \
    -Wl,-Map,rngcheck.map \
    "$root/../experimental/persistent-entropy/check.c" \
    "$root/../experimental/persistent-entropy/entropy.c" \
    "$br/src/rand/hmac_drbg.c" "$br/src/mac/hmac.c" \
    "$br/src/hash/sha2small.c" "$br/src/codec/dec32be.c" \
    "$br/src/codec/enc32be.c" -o rngcheck
ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 rngcheck.elf > rngcheck.dis
python3 "$root/tools/isa-audit.py" rngcheck rngcheck.elf rngcheck.dis \
    --map rngcheck.map --output rngcheck-audit.json
