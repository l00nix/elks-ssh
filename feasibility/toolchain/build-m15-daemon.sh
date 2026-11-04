#!/bin/sh
# MIT. Separate feasibility binaries; never installs or starts a service.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to a prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out="$root/feasibility/build/m15-daemon"
mkdir -p "$out/audit-tools"
cp "$root/feasibility/tools/retain-elf2elks.py" "$out/audit-tools/elf2elks"
chmod +x "$out/audit-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$out/audit-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$root"
for entropy in 0 1; do
    name=dropbear-m15
    if test "$entropy" = 1; then name=dropbear-m15-qemu; fi
    make -f feasibility/toolchain/Makefile.m15 TEST_ENTROPY="$entropy" \
        CC="ia16-elf-gcc -Wl,-Map,$out/$name.map"
    cp "$name" "$name.elf" "$out/"
done
for name in edbench m15bench; do
    make -f feasibility/toolchain/Makefile.m15 TEST_ENTROPY=0 "$name" \
        CC="ia16-elf-gcc -Wl,-Map,$out/$name.map"
    cp "$name" "$name.elf" "$out/"
done
for name in dropbear-m15 dropbear-m15-qemu edbench m15bench; do
    ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$out/$name.elf" > "$out/$name.dis"
    python3 feasibility/tools/isa-audit.py "$out/$name" "$out/$name.elf" "$out/$name.dis" \
        --map "$out/$name.map" --output "$out/$name-audit.json"
done
