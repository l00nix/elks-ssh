#!/bin/sh
# MIT. Public-pattern filesystem probe, never installed on physical hardware.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to a prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out=${ELKSSH_STORE_OUT:-"$root/build/store"}
mkdir -p "$out/audit-tools"
out=$(CDPATH= cd -- "$out" && pwd)
cp "$root/tools/retain-elf2elks.py" "$out/audit-tools/elf2elks"
chmod +x "$out/audit-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$out/audit-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$out"
ia16-elf-gcc -mcmodel=medium -melks-libc -march=i8086 -mtune=i8086 \
    -Os -Wall -Wextra -Werror -maout-heap=1024 -maout-stack=2048 \
    -Wl,-Map,storeprobe.map "$root/src/storeprobe.c" -o storeprobe
ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 storeprobe.elf > storeprobe.dis
python3 "$root/tools/isa-audit.py" storeprobe storeprobe.elf storeprobe.dis \
    --map storeprobe.map --output storeprobe-audit.json
