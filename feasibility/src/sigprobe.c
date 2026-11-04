/* MIT. Register and restore this process's signal handlers; send no signals. */
#include <stdio.h>
#include <signal.h>
#include <errno.h>

#ifdef __ia16__
#if defined(__TINY__) || defined(__SMALL__) || defined(__COMPACT__)
extern __attribute__((near_section, __stdcall__)) __far void _signal_cbhandler(int);
#else
extern __far void __attribute__((__stdcall__)) _signal_cbhandler(int);
#endif
#endif

static void handler(int sig) { (void)sig; }

int main(void)
{
    static const int signals[] = { SIGINT, SIGTERM, SIGPIPE, SIGCHLD, SIGSEGV };
    static const char *names[] = { "SIGINT", "SIGTERM", "SIGPIPE", "SIGCHLD", "SIGSEGV" };
    unsigned i;
    int mode, failures = 0;
    sighandler_t old;
    puts("ELKS SSH signal registration probe (no signals sent)");
#ifdef __ia16__
    {
        unsigned long address = (unsigned long)_signal_cbhandler;
        printf("libc callback=%04x:%04x\n", (unsigned)(address >> 16),
               (unsigned)address);
    }
#endif
    for (i = 0; i < sizeof(signals)/sizeof(signals[0]); i++) {
        for (mode = 0; mode < 2; mode++) {
            errno = 0;
            old = signal(signals[i], mode ? handler : SIG_IGN);
            if (old == SIG_ERR) {
                printf("%s %s: FAIL errno=%d\n", names[i], mode ? "handler" : "ignore", errno);
                failures++;
            } else {
                printf("%s %s: OK\n", names[i], mode ? "handler" : "ignore");
                if (signal(signals[i], old) == SIG_ERR) {
                    printf("restore: FAIL errno=%d\n", errno);
                    failures++;
                }
            }
        }
    }
    printf("RESULT failures=%d\n", failures);
    return failures ? 1 : 0;
}
