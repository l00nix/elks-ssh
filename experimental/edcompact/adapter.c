/* MIT. Checks and ABI adaptation around unchanged c25519 Ed25519 code.
 * All early-return checks concern public inputs, not signing secrets.
 * This is an isolated experiment, not a production backend.
 */
#ifndef ELKSSH_EDCOMPACT_EXPERIMENT
#error Experimental build only
#endif
#include <stddef.h>
#include <string.h>
#include "adapter.h"
#include "edsign.h"

int ge25519_is_canonical(const unsigned char *p);
int ge25519_has_small_order(const unsigned char p[32]);

static int scalar_canonical(const unsigned char *s)
{
    static const unsigned char order[32] = {
        0xed,0xd3,0xf5,0x5c,0x1a,0x63,0x12,0x58,
        0xd6,0x9c,0xf7,0xa2,0xde,0xf9,0xde,0x14,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0x10
    };
    int i;
    for (i=31; i>=0; i--) {
        if (s[i] < order[i]) return 1;
        if (s[i] > order[i]) return 0;
    }
    return 0;
}

static int point_encoding(const unsigned char *p)
{
    return ge25519_is_canonical(p) && !ge25519_has_small_order(p);
}

int elkssh_edcompact_sign(unsigned char signature[64],
    const unsigned char public_key[32], const unsigned char seed[32],
    const unsigned char *message, unsigned long length)
{
    /* c25519's SHA-512 total_size << 3 uses 16-bit size_t on ELKS.
     * This bound also protects prefix additions and block-loop arithmetic.
     * It exceeds this build's 2048-byte SSH transmit payload limit.
     */
    if (length > ELKSSH_EDCOMPACT_MAX_MESSAGE || !point_encoding(public_key)) {
        memset(signature,0,64);
        return -1;
    }
    edsign_sign(signature, public_key, seed, message, (size_t)length);
    return 0;
}

int elkssh_edcompact_verify(const unsigned char *signature, unsigned long slen,
    const unsigned char public_key[32], const unsigned char *message,
    unsigned long length)
{
    /* Check length before touching signature bytes, including hostile lengths. */
    if (slen != 64 || length > ELKSSH_EDCOMPACT_MAX_MESSAGE) return -1;
    if (!scalar_canonical(signature+32) || !point_encoding(signature) ||
            !point_encoding(public_key)) return -1;
    /* Upstream verifies point decompression and the uncofactored equation. */
    return edsign_verify(signature, public_key, message, (size_t)length) ? 0 : -1;
}
