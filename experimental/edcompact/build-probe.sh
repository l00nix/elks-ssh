#!/bin/sh
# MIT. Public-vector probe, not a service.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out=${ELKSSH_EDPROBE_OUT:-"$root/feasibility/build/edcompact-probe"}
mkdir -p "$out/tools"
out=$(CDPATH= cd -- "$out" && pwd)
cp "$root/feasibility/tools/retain-elf2elks.py" "$out/tools/elf2elks"
chmod +x "$out/tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$out/tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$root"
v=feasibility/vendor/c25519
if [ -n "${ELKSSH_EDPROBE_OBJECTS:-}" ]; then
 set --
 for name in edsign ed25519 f25519 fprime sha512 adapter point-checks; do
  test -f "$ELKSSH_EDPROBE_OBJECTS/edcompact-$name.o"
  set -- "$@" "$ELKSSH_EDPROBE_OBJECTS/edcompact-$name.o"
 done
else
 set -- experimental/edcompact/adapter.c experimental/edcompact/point-checks.c \
  "$v/edsign.c" "$v/ed25519.c" "$v/f25519.c" "$v/fprime.c" "$v/sha512.c"
fi
ia16-elf-gcc -mcmodel=medium -melks-libc -march=i8086 -mtune=i8086 -Os -Wall \
 -Werror=implicit-function-declaration -Werror=incompatible-pointer-types -fstack-usage \
 -maout-heap=4096 -maout-stack=8192 -DELKSSH_EDCOMPACT_EXPERIMENT \
 -Iexperimental/edcompact -I"$v" -Wl,-Map,"$out/edcheck.map" \
 experimental/edcompact/tests/check.c "$@" -o "$out/edcheck"
ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$out/edcheck.elf" > "$out/edcheck.dis"
python3 feasibility/tools/isa-audit.py "$out/edcheck" "$out/edcheck.elf" \
 "$out/edcheck.dis" --map "$out/edcheck.map" --output "$out/edcheck-audit.json"
