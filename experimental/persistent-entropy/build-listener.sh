#!/bin/sh
# MIT. Isolated userspace memory experiment; never installs a service.
set -eu
: "${ELKSSH_ELKS:?Set ELKSSH_ELKS to the prepared ELKS checkout}"
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TOPDIR=$(CDPATH= cd -- "$ELKSSH_ELKS" && pwd); export TOPDIR
out=${ELKSSH_LISTENER_OUT:-"$root/feasibility/build/inetd-listener"}
mkdir -p "$out" "$root/feasibility/build/listener-tools"
out=$(CDPATH= cd -- "$out" && pwd)
cp "$root/feasibility/tools/retain-elf2elks.py" "$root/feasibility/build/listener-tools/elf2elks"
chmod +x "$root/feasibility/build/listener-tools/elf2elks"
export ELKSSH_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$root/feasibility/build/listener-tools:$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
cd "$root"
ia16-elf-gcc -mcmodel=medium -melks-libc -march=i8086 -mtune=i8086 -Os -Wall \
    -Werror=implicit-function-declaration -Werror=incompatible-pointer-types \
    -DELKSSH_INETD_EXPERIMENT -maout-heap=4096 -maout-stack=4096 \
    -Wl,-Map,"$out/sshlisten.map" -o "$out/sshlisten" experimental/persistent-entropy/inetd-listener.c
ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 "$out/sshlisten.elf" > "$out/sshlisten.dis"
python3 feasibility/tools/isa-audit.py "$out/sshlisten" "$out/sshlisten.elf" \
    "$out/sshlisten.dis" --map "$out/sshlisten.map" --output "$out/sshlisten-audit.json"
