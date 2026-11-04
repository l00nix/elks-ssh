/* MIT. RFC 8032 test 1, public seed only. Never a key-generation utility. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "curve25519.h"

/* The unused upstream key-generation entry point references this symbol.
 * Any accidental call is fatal; no fixed-seed RNG is supplied. */
void genrandom(unsigned char *buf, unsigned int len)
{
    (void)buf; (void)len;
    fputs("FAIL unexpected RNG request\n", stderr);
    exit(2);
}

static unsigned char nibble(char c) { return c <= '9' ? c-'0' : c-'a'+10; }
static void decode(unsigned char *out, const char *hex, unsigned n)
{
    unsigned i;
    for (i=0; i<n; i++) out[i]=(nibble(hex[2*i])<<4)|nibble(hex[2*i+1]);
}
static int failures;
static void result(const char *name, int ok, time_t start)
{
    printf("%s %s seconds=%ld\n", ok ? "PASS" : "FAIL", name,
           (long)(time(NULL)-start));
    fflush(stdout);
    if (!ok) failures++;
}
int main(void)
{
    unsigned char seed[32], public[32], want[64], signature[64], empty[1]={0};
    unsigned long len=0;
    time_t start, all=time(NULL);
    decode(seed,"9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",32);
    decode(public,"d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",32);
    decode(want,"e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
                "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",64);
    puts("Ed25519 public RFC 8032 probe; no key generation");
    fflush(stdout);
    start=time(NULL);
    dropbear_ed25519_sign(empty,0,signature,&len,seed,public);
    result("sign-rfc8032",len==64 && !memcmp(signature,want,64),start);
    start=time(NULL);
    result("verify-rfc8032",dropbear_ed25519_verify(empty,0,want,64,public)==0,start);
    want[0]^=1;
    start=time(NULL);
    result("reject-tampered",dropbear_ed25519_verify(empty,0,want,64,public)!=0,start);
    start=time(NULL);
    result("reject-short",dropbear_ed25519_verify(empty,0,want,63,public)!=0,start);
    printf("RESULT %s checks=4 failures=%d seconds=%ld\n",
           failures ? "FAIL" : "PASS",failures,(long)(time(NULL)-all));
    return failures ? 1 : 0;
}
