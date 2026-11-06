#!/bin/sh
# MIT. Separate diagnostic executable; never installs or starts a service.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to the prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
case ${ELKSSH_TRACE_X25519:-baseline} in
    baseline) variant=trace; program=sshtrace; link_extra= ;;
    m15) variant=trace-m15; program=sshfast; link_extra= ;;
    *) echo 'Unsupported diagnostic X25519 backend' >&2; exit 2 ;;
esac
out=${ELKSSH_TRACE_OUT:-"$root/feasibility/build/persistent-$variant"}
mkdir -p "$out" "$root/feasibility/build/persistent-trace-tools"
out=$(CDPATH= cd -- "$out" && pwd)
cp "$root/feasibility/tools/retain-elf2elks.py" "$root/feasibility/build/persistent-trace-tools/elf2elks"
chmod +x "$root/feasibility/build/persistent-trace-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$root/feasibility/build/persistent-trace-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$root"
make -f experimental/persistent-entropy/Makefile.$variant \
    PERSIST_OBJDIR="$out/objects" PERSIST_OUTPUT="$out/$program" \
    CC="ia16-elf-gcc -Wl,-Map,$out/$program.map $link_extra"
ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$out/$program.elf" > "$out/$program.dis"
python3 feasibility/tools/isa-audit.py "$out/$program" "$out/$program.elf" \
    "$out/$program.dis" --map "$out/$program.map" --output "$out/$program-audit.json"
