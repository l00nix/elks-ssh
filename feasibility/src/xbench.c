/* MIT. Public-vector performance comparison, not production crypto or SSH. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#ifdef USE_BEARSSL
#include "bearssl_ec.h"
#else
#include "curve25519.h"
#endif
#ifndef BACKEND_NAME
#define BACKEND_NAME "dropbear"
#endif
struct vector { const char *name, *scalar, *point, *expected; };
#include "x25519-vectors.h"
typedef char need32[sizeof(uint32_t)==4?1:-1];
static unsigned char nibble(char c) { return c<='9'?c-'0':c-'a'+10; }
static void decode(unsigned char *p,const char *h) {
    unsigned i; for(i=0;i<32;i++) p[i]=(nibble(h[2*i])<<4)|nibble(h[2*i+1]);
}
int main(int argc,char **argv) {
    unsigned i, count=sizeof(vectors)/sizeof(vectors[0]);
    int failures=0, ok;
    unsigned char k[32],p[32],out[32],want[32];
    time_t start, all=time(NULL);
    if(argc==2 && !strcmp(argv[1],"quick")) count=1;
    else if(argc!=1) { puts("usage: xbench [quick]"); return 2; }
    printf("X25519 comparative probe: %s\n",BACKEND_NAME);
    printf("ABI int=%u long=%u pointer=%u; public vectors only\n",
        (unsigned)sizeof(int),(unsigned)sizeof(long),(unsigned)sizeof(void *));
    fflush(stdout);
    for(i=0;i<count;i++) {
        decode(k,vectors[i].scalar); decode(p,vectors[i].point);
        decode(want,vectors[i].expected);
        start=time(NULL);
#ifdef USE_BEARSSL
        /* This specific Curve25519 implementation copies/clamps little-endian k. */
        memcpy(out,p,32);
        ok=br_ec_c25519_m15.mul(out,32,k,32,BR_EC_curve25519)==1;
#else
        dropbear_curve25519_scalarmult(out,k,p); ok=1;
#endif
        ok=ok && !memcmp(out,want,32);
        printf("%s %s seconds=%ld\n",ok?"PASS":"FAIL",vectors[i].name,
               (long)(time(NULL)-start));
        fflush(stdout); if(!ok) failures++;
    }
    printf("RESULT %s checks=%u failures=%d seconds=%ld\n",
           failures?"FAIL":"PASS",count,failures,(long)(time(NULL)-all));
    return failures?1:0;
}
