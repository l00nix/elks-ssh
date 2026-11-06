/* MIT. For crypto_desc.o only in the isolated Ed25519 comparison.
 * Ed25519 uses c25519's SHA-512. No enabled SSH algorithm needs LTC SHA-512.
 * Keep normal feature/header definitions everywhere else, including key APIs.
 */
#include "includes.h"
#if DROPBEAR_SHA2_512_HMAC || DROPBEAR_ECC_521 || DROPBEAR_SHA384 || DROPBEAR_DH_GROUP16 || DROPBEAR_SNTRUP761
#error Cannot omit LTC SHA-512 with another enabled consumer
#endif
#undef DROPBEAR_SHA512
#define DROPBEAR_SHA512 0
