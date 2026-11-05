/* MIT. Never prints seed bytes. No keys, network listener or SSH session. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include "entropy.h"
int main(int argc,char **argv) {
    unsigned char a[32],b[32];
    int pid,status;
    if (argc==2 && !strcmp(argv[1],"fail")) {
        memset(a,0xa5,32); memset(b,0xa5,32);
        if (elkssh_serial_getrandom(a,32,0)!=-1 || memcmp(a,b,32)) return 2;
        if (elkssh_serial_getrandom(a,32,0)!=-1 || memcmp(a,b,32)) return 3;
        puts("PASS refusal, unchanged output, poisoned retry"); return 0;
    }
    if (elkssh_serial_getrandom(a,32,0)!=32) { puts("FAIL initial seed"); return 1; }
    if (elkssh_serial_getrandom(b,32,0)!=32 || !memcmp(a,b,32)) { puts("FAIL second seed"); return 1; }
    pid=fork();
    if (pid<0) { puts("FAIL fork"); return 1; }
    if (!pid) {
        int ok=elkssh_serial_getrandom(b,32,0)==32 && memcmp(a,b,32);
        memset(a,0,32); memset(b,0,32); _exit(ok?0:1);
    }
    if (waitpid(pid,&status,0)!=pid || status) { puts("FAIL child seed"); return 1; }
    if (elkssh_serial_getrandom(b,32,0)!=32 || !memcmp(a,b,32)) { puts("FAIL parent seed"); return 1; }
    memset(a,0,32); memset(b,0,32);
    puts("PASS four seeds across parent and child; no bytes logged");
    return 0;
}
