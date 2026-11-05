#!/bin/sh
# MIT. Isolated experimental server; does not install or start a service.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to the prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out=${ELKSSH_PERSIST_SERVER_OUT:-"$root/feasibility/build/persistent-server"}
mkdir -p "$out" "$root/feasibility/build/persistent-audit-tools"
out=$(CDPATH= cd -- "$out" && pwd)
# Keep this executable wrapper on the checkout filesystem even if large build
# artifacts are directed to a noexec tmpfs to avoid exhausting build-host disk.
cp "$root/feasibility/tools/retain-elf2elks.py" "$root/feasibility/build/persistent-audit-tools/elf2elks"
chmod +x "$root/feasibility/build/persistent-audit-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$root/feasibility/build/persistent-audit-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$root"
make -f experimental/persistent-entropy/Makefile \
    PERSIST_OBJDIR="$out/objects" PERSIST_OUTPUT="$out/dropbear-persistent" \
    CC="ia16-elf-gcc -Wl,-Map,$out/dropbear-persistent.map"
ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$out/dropbear-persistent.elf" > "$out/dropbear-persistent.dis"
python3 feasibility/tools/isa-audit.py "$out/dropbear-persistent" "$out/dropbear-persistent.elf" \
    "$out/dropbear-persistent.dis" --map "$out/dropbear-persistent.map" \
    --output "$out/dropbear-persistent-audit.json"
