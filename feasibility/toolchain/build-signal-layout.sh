#!/bin/sh
# MIT. Reproduce callback placement without editing the prepared ELKS tree.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to the prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd)
export TOPDIR
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
out=${ELKSSH_SIGNAL_OUT:-"$root/build/signal-layout"}
mkdir -p "$out/audit-tools"
out=$(CDPATH= cd -- "$out" && pwd)
cp "$root/tools/retain-elf2elks.py" "$out/audit-tools/elf2elks"
chmod +x "$out/audit-tools/elf2elks"
export PATH="$out/audit-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$out"
flags='-mcmodel=medium -melks-libc -march=i8086 -mtune=i8086 -Os -Wall -maout-heap=2048 -maout-stack=2048'
libc=$(ia16-elf-gcc $flags -print-file-name=libc.a)
ia16-elf-ar p "$libc" signalcb.o > callback.o
test -s callback.o
ia16-elf-gcc $flags -c "$root/src/sigprobe.c" -o probe.o
ia16-elf-gcc $flags -c "$root/src/siglife.c" -o life.o
ia16-elf-gcc $flags -c "$root/src/sigpad.S" -o pad.o
ia16-elf-gcc $flags -c -DFAR_PAD=0 "$root/src/sigpad.S" -o padnear.o
ia16-elf-gcc $flags -Wl,-Map,sig-near.map -o sig-near padnear.o probe.o
ia16-elf-gcc $flags -Wl,-Map,sig-large.map -o sig-large pad.o probe.o
ia16-elf-gcc $flags -Wl,-Map,sig-early.map -o sig-early callback.o pad.o probe.o
ia16-elf-gcc $flags -Wl,-Map,sig-life.map -o sig-life callback.o pad.o life.o
for name in sig-near sig-large sig-early sig-life; do
    ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$name.elf" > "$name.dis"
    python3 "$root/tools/isa-audit.py" "$name" "$name.elf" "$name.dis" \
        --map "$name.map" --output "$name-audit.json"
done
