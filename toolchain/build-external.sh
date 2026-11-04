#!/bin/sh
# Minimal ELKS external build entry point. Neither target is release ready.
set -eu
TOPDIR=${ELKSSH_ELKS:-${TOPDIR:-}}
: "${TOPDIR:?Set TOPDIR or ELKSSH_ELKS to a prepared ELKS checkout}"
TOPDIR=$(CDPATH= cd -- "$TOPDIR" && pwd)
export TOPDIR
PATH="$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
export PATH
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
program=${ELKSSH_PROGRAM:-dbclient}
case "$program" in dbclient|dropbear) ;; *) echo 'Use ELKSSH_PROGRAM=dbclient or dropbear' >&2; exit 2;; esac
make -f Makefile.elks PROGRAM="$program" clean
make -f Makefile.elks PROGRAM="$program"
printf '%s\n' "Built experimental $program; QEMU test login is validated, deployment is not."
printf '%s\n' 'Connections must fail if the configured strong random source is unavailable.'
