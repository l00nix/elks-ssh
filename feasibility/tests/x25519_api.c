/* MIT. Host differential-test entry point; not linked into ELKS binaries. */
#include <string.h>
#ifdef USE_BEARSSL
#include "bearssl_ec.h"
#else
#include "curve25519.h"
#endif
int probe_x25519(unsigned char *out, const unsigned char *k, const unsigned char *p) {
#ifdef USE_BEARSSL
    memcpy(out,p,32);
    return br_ec_c25519_m15.mul(out,32,k,32,BR_EC_curve25519)==1;
#else
    dropbear_curve25519_scalarmult(out,k,p);
    return 1;
#endif
}
