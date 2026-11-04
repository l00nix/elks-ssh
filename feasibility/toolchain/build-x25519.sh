#!/bin/sh
# MIT. Comparative probes only; no daemon or prepared ELKS-tree changes.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to a prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out=${ELKSSH_XBENCH_OUT:-"$root/build/x25519"}
mkdir -p "$out/audit-tools"
out=$(CDPATH= cd -- "$out" && pwd)
cp "$root/tools/retain-elf2elks.py" "$out/audit-tools/elf2elks"
chmod +x "$out/audit-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$out/audit-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$out"
flags='-mcmodel=medium -melks-libc -march=i8086 -mtune=i8086 -Os -Wall -Wextra -fwrapv -fstack-usage -Werror=overflow -Werror=shift-count-overflow -Werror=implicit-function-declaration -Werror=incompatible-pointer-types -maout-heap=1024 -maout-stack=8192'
for slow in 0 1; do
    ia16-elf-gcc $flags -DBR_NO_ARITH_SHIFT=1 -DBR_SLOW_MUL15=$slow \
        -DUSE_BEARSSL -DBACKEND_NAME=\"m15-$slow\" \
        -I"$root/vendor/bearssl/inc" -I"$root/vendor/bearssl/src" \
        -Wl,-Map,xm15-$slow.map "$root/src/xbench.c" \
        "$root/vendor/bearssl/src/ec/ec_c25519_m15.c" \
        "$root/vendor/bearssl/src/codec/ccopy.c" -o xm15-$slow
    cp ec_c25519_m15.su xm15-$slow-stack.txt
done
ia16-elf-gcc $flags -I"$root/tests/shim" -I"$root/vendor/dropbear/src" \
    -Wl,-Map,xbase.map "$root/src/xbench.c" \
    "$root/vendor/dropbear/src/curve25519.c" -o xbase
cp curve25519.su xbase-stack.txt
for name in xbase xm15-0 xm15-1; do
    ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$name.elf" > "$name.dis"
    python3 "$root/tools/isa-audit.py" "$name" "$name.elf" "$name.dis" \
        --map "$name.map" --output "$name-audit.json"
done
