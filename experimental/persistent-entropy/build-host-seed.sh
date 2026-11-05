#!/bin/sh
# MIT. Build only the native host helper; no ELKS cross compiler required.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
br="$here/../../feasibility/vendor/bearssl"
out=${1:?Pass a new or existing private build directory}
mkdir -p "$out"
cc -O2 -Wall -Wextra -Werror -DBR_NO_ARITH_SHIFT=1 \
    -I"$br/inc" -I"$br/src" "$here/seed-record.c" \
    "$br/src/rand/hmac_drbg.c" "$br/src/mac/hmac.c" \
    "$br/src/hash/sha2small.c" "$br/src/codec/dec32be.c" \
    "$br/src/codec/enc32be.c" -o "$out/seed-record"
