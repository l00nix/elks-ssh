/* MIT. Experimental X25519 adapter; timing qualification is still open. */
#ifndef ELKSSH_M15_EXPERIMENT
#error This adapter is restricted to the isolated feasibility build
#endif
#include "includes.h"
#include "dbutil.h"
#include "bearssl_ec.h"

void elkssh_m15_scalarmult(unsigned char *out, const unsigned char *scalar,
                          const unsigned char *point)
{
    /* This specific upstream implementation accepts little-endian scalars.
     * KEX still validates peer length and rejects an all-zero shared secret. */
    memcpy(out, point, 32);
    if (br_ec_c25519_m15.mul(out, 32, scalar, 32, BR_EC_curve25519) != 1)
        dropbear_exit("Experimental X25519 failure");
}
