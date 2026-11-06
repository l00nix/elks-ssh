/* Isolated public-vector performance probe only, NOT an SSH backend.
 * Upstream c25519 verification lacks required strict RFC 8032 validation.
 * Never use this bridge for authentication or real private keys.
 */
#include "curve25519.h"
#include "edsign.h"
#include <stdlib.h>
void dropbear_ed25519_sign(const unsigned char *m, unsigned long n,
 unsigned char *s, unsigned long *sn, const unsigned char *sk,
 const unsigned char *pk)
{
 if (n != 0) abort(); /* This comparison uses only the empty public fixture. */
 edsign_sign(s,pk,sk,m,0); *sn=64;
}
int dropbear_ed25519_verify(const unsigned char *m, unsigned long n,
 const unsigned char *s, unsigned long sn, const unsigned char *pk)
{
 if (sn!=64 || n!=0) return -1;
 return edsign_verify(s,pk,m,0) ? 0 : -1;
}
