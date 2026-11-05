#!/bin/sh
# MIT. External user-space probe; never installs or starts a daemon.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to the prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out="$root/feasibility/build/serial-entropy"
mkdir -p "$out/audit-tools"
cp "$root/feasibility/tools/retain-elf2elks.py" "$out/audit-tools/elf2elks"
chmod +x "$out/audit-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$out/audit-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$root"
for model in hardware qemu; do
    device=/dev/ttyS0
    test "$model" != qemu || device=/dev/ttyS1
    ia16-elf-gcc -mcmodel=medium -melks-libc -march=i8086 -mtune=i8086 \
        -Os -Wall -Werror -maout-heap=1024 -maout-stack=4096 \
        "-DELKSSH_ENTROPY_DEVICE=\"$device\"" \
        -Wl,-Map,"$out/eprobe-$model.map" \
        experimental/serial-entropy/probe.c experimental/serial-entropy/entropy.c \
        -o "$out/eprobe-$model"
    ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$out/eprobe-$model.elf" > "$out/eprobe-$model.dis"
    python3 feasibility/tools/isa-audit.py "$out/eprobe-$model" "$out/eprobe-$model.elf" \
        "$out/eprobe-$model.dis" --map "$out/eprobe-$model.map" --output "$out/eprobe-$model-audit.json"
done
