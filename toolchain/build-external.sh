#!/bin/sh
# Minimal ELKS external build entry point. Currently builds dbclient only.
set -eu
TOPDIR=${ELKSSH_ELKS:-${TOPDIR:-}}
: "${TOPDIR:?Set TOPDIR or ELKSSH_ELKS to a prepared ELKS checkout}"
TOPDIR=$(CDPATH= cd -- "$TOPDIR" && pwd)
export TOPDIR
PATH="$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
export PATH
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
make -f Makefile.elks clean
make -f Makefile.elks
printf '%s\n' 'Built experimental dbclient only; no ELKS sshd is implemented yet.'
printf '%s\n' 'Connections must fail if the configured strong random source is unavailable.'
