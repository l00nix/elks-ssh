/* MIT. Isolated memory experiment, not a production inetd replacement.
 * Single concurrent worker. SSH protocol/authentication remain in Dropbear -i.
 * No randomness, key handling or configuration supplied by the peer.
 */
#ifndef ELKSSH_INETD_EXPERIMENT
#error Experimental listener only
#endif
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <unistd.h>
#include <signal.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

/* This ELKS libc lacks sig_atomic_t; a native 16-bit flag is used here. */
static volatile int stopping;
static void stop(int sig) { (void)sig; stopping = 1; }

static void reap(pid_t *child)
{
    if (*child && waitpid(*child, NULL, WNOHANG) == *child) *child = 0;
}

int main(int argc, char **argv)
{
    struct sockaddr_in address;
    int listener, accepted, ready, i;
    pid_t child = 0, result;
    char *end;
    unsigned long port;

    if (argc < 4 || argv[2][0] != '/' || strcmp(argv[3], "-i")) {
        fprintf(stderr, "Usage: sshlisten port /absolute/server -i [options]\n");
        return 2;
    }
    port = strtoul(argv[1], &end, 10);
    if (!*argv[1] || *end || port < 1 || port > 65535UL) return 2;
    if (signal(SIGTERM, stop) == SIG_ERR || signal(SIGINT, stop) == SIG_ERR ||
            signal(SIGCHLD, SIG_DFL) == SIG_ERR)
        return 1;
    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) { perror("sshlisten socket"); return 1; }
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons((unsigned short)port);
    address.sin_addr.s_addr = INADDR_ANY;
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) < 0 ||
            listen(listener, 1) < 0) {
        perror("sshlisten bind/listen"); close(listener); return 1;
    }
    fprintf(stderr, "sshlisten ready; one concurrent worker\n"); fflush(stderr);
    while (!stopping) {
        fd_set reads;
        struct timeval timeout;
        reap(&child);
        FD_ZERO(&reads); FD_SET(listener, &reads);
        timeout.tv_sec = 1; timeout.tv_usec = 0;
        ready = select(listener + 1, &reads, NULL, NULL, &timeout);
        if (ready < 0) {
            if (stopping) break;
            if (errno == EINTR) continue;
            perror("sshlisten select"); break;
        }
        if (!ready || stopping) continue;
        accepted = accept(listener, NULL, NULL);
        if (accepted < 0) {
            /* ELKS can expose ERESTARTSYS (512) after the stop signal.
             * The flag, not a particular interrupted-syscall errno,
             * determines whether this is an intentional shutdown. */
            if (stopping) break;
            if (errno != EINTR) perror("sshlisten accept");
            continue;
        }
        if (stopping) { close(accepted); break; }
        reap(&child);
        if (child) { close(accepted); continue; }
        result = fork();
        if (result == (pid_t)-1) {
            perror("sshlisten fork"); close(accepted); continue;
        }
        if (result == 0) {
            close(listener);
            signal(SIGTERM, SIG_DFL); signal(SIGINT, SIG_DFL);
            if (dup2(accepted, 0) < 0 || dup2(accepted, 1) < 0) _exit(126);
            if (accepted > 1) close(accepted);
            execv(argv[2], &argv[2]);
            perror("sshlisten execv"); _exit(127);
        }
        child = result;
        close(accepted);
    }
    close(listener);
    reap(&child);
    if (child) {
        kill(child, SIGTERM);
        for (i = 0; child && i < 20; i++) {
            struct timeval pause;
            pause.tv_sec = 0; pause.tv_usec = 100000;
            select(0, NULL, NULL, NULL, &pause);
            reap(&child);
        }
        if (child) {
            kill(child, SIGKILL);
            while (waitpid(child, NULL, 0) == (pid_t)-1 && errno == EINTR) {}
        }
    }
    return stopping ? 0 : 1;
}
