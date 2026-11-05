#!/bin/sh
# MIT. Existing Dropbear key utility, isolated serial-entropy variants.
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
for mode in 0 1; do
    name=dropbearkey-serial
    test "$mode" != 1 || name=dropbearkey-serial-qemu
    make -f experimental/serial-entropy/Makefile.keygen SERIAL_QEMU="$mode" \
        CC="ia16-elf-gcc -Wl,-Map,$out/$name.map"
    cp "$name" "$name.elf" "$out/"
    ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$out/$name.elf" > "$out/$name.dis"
    python3 feasibility/tools/isa-audit.py "$out/$name" "$out/$name.elf" "$out/$name.dis" \
        --map "$out/$name.map" --output "$out/$name-audit.json"
done
