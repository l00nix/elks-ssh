/* MIT. Public fixture only. Do not point this executable at real RNG state. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include "entropy.h"
static unsigned int stop_stage;
static int contend;
static int one(void);
void elkssh_rng_stage(unsigned int stage)
{
    pid_t pid;
    int status;
    printf("STAGE %u\n", stage); fflush(stdout);
    if (stage == 1 && contend) {
        contend = 0;
        pid = fork();
        if (pid == (pid_t)-1) _exit(91);
        if (!pid) _exit(one() == 1 ? 0 : 1);
        if (waitpid(pid, &status, 0) != pid || status) _exit(92);
        puts("PASS competing child refused while parent holds lock");
    }
    if (stage == stop_stage) {
        char c;
        if (read(0, &c, 1) != 1) _exit(90);
    }
}
static int one(void)
{
    unsigned char bytes[32], guard[32];
    unsigned int i;
    memset(bytes, 0xa5, sizeof bytes); memcpy(guard, bytes, sizeof guard);
    if (elkssh_persistent_getrandom(bytes, sizeof bytes, 0) != 32) {
        if (memcmp(bytes, guard, sizeof bytes)
            || elkssh_persistent_getrandom(bytes, sizeof bytes, 0) != -1
            || memcmp(bytes, guard, sizeof bytes)) {
            puts("FAIL refusal modified output or retry succeeded"); return 2;
        }
        puts("REFUSED output unchanged; process retry refused"); return 1;
    }
    printf("PUBLIC-FIXTURE ");
    for (i=0; i<sizeof bytes; i++) printf("%02x", bytes[i]);
    putchar('\n'); fflush(stdout); return 0;
}
int main(int argc, char **argv)
{
    pid_t pid;
    int status;
    if (argc == 2 && !strcmp(argv[1], "contend")) {
        contend = 1;
        return one();
    }
    if (argc == 2 && !strcmp(argv[1], "fork")) {
        if (one()) return 1;
        pid = fork();
        if (pid == (pid_t)-1) return 2;
        if (!pid) _exit(one());
        if (waitpid(pid, &status, 0) != pid || status) return 2;
        return one();
    }
    if (argc == 2) stop_stage = (unsigned int)atoi(argv[1]);
    return one();
}
