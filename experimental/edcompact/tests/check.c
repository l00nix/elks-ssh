/* MIT. Public fixtures only. Never generate or load runtime SSH keys. */
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "adapter.h"
static unsigned char message[4097], seed[32], pub[32], sig[96], output[64];
static unsigned word(const unsigned char *s) { return s[0] | ((unsigned)s[1] << 8); }
int main(int argc, char **argv)
{
    FILE *f;
    unsigned char h[7], magic[4];
    unsigned count=0, failures=0, accepted=0;
    time_t all=time(NULL);
    if (argc!=2 || !(f=fopen(argv[1],"rb"))) return 2;
    if (fread(magic,1,4,f)!=4 || memcmp(magic,"EDC1",4)) return 2;
    puts("ED25519 PUBLIC VECTOR PROBE - NO SSH LOGIN"); fflush(stdout);
    while (fread(h,1,7,f)==7) {
        unsigned id=word(h+1), len=word(h+3), slen=h[5], expected=h[6];
        int ok, valid=0;
        time_t start=time(NULL);
        if (h[0]>2 || slen>96 || expected>2 || (h[0]!=2 && len>sizeof(message))) return 2;
        if (fread(seed,1,32,f)!=32 || fread(pub,1,32,f)!=32 ||
                fread(sig,1,96,f)!=96) return 2;
        if (h[0]!=2 && fread(message,1,len,f)!=len) return 2;
        if (h[0]==1) {
            valid=elkssh_edcompact_sign(output,pub,seed,message,len)==0;
            ok=valid==(int)expected && (!valid || !memcmp(output,sig,64));
        } else if (h[0]==2) {
            /* NULL proves oversized input is refused before dereference. */
            ok=elkssh_edcompact_verify(NULL,64,NULL,NULL,len)!=0 &&
               elkssh_edcompact_sign(output,NULL,NULL,NULL,len)!=0;
        } else {
            valid=elkssh_edcompact_verify(sig,slen,pub,message,len)==0;
            ok=expected==2 || valid==(int)expected;
        }
        if (!ok) failures++;
        if (valid) accepted++;
        count++;
        printf("%s case=%u op=%u accepted=%d seconds=%ld\n",ok?"PASS":"FAIL",id,h[0],valid,(long)(time(NULL)-start));
        fflush(stdout);
    }
    if (ferror(f) || !feof(f)) return 2;
    fclose(f);
    printf("RESULT %s checks=%u failures=%u accepted=%u seconds=%ld\n",
        failures?"FAIL":"PASS",count,failures,accepted,(long)(time(NULL)-all));
    return failures?1:0;
}
