/* MIT. Own-process delivery and child reaping; no external process signalled. */
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <sys/wait.h>
#include <errno.h>

/* ELKS has no sig_atomic_t typedef; its native int is one 16-bit word. */
static volatile int delivered, children;
static void handler(int sig)
{
    if (sig == SIGUSR1) delivered++;
    if (sig == SIGCHLD) children++;
}

int main(void)
{
    int i, status, failures = 0;
    pid_t child, waited;
    struct sigaction action;
    puts("ELKS SSH signal delivery/reaping probe (own process/children only)");
    action.sa_handler = handler;
    action.sa_flags = SA_NOCLDSTOP;
    sigemptyset(&action.sa_mask);
    if (signal(SIGUSR1, handler) == SIG_ERR ||
        sigaction(SIGCHLD, &action, 0) < 0 ||
        signal(SIGALRM, SIG_DFL) == SIG_ERR) {
        printf("FAIL registration errno=%d\n", errno);
        return 1;
    }
    /* A stuck wait terminates only this test process. */
    alarm(10);
    for (i = 0; i < 8; i++) {
        /* ELKS resets caught signals to SIG_DFL after delivery. */
        if (signal(SIGUSR1, handler) == SIG_ERR ||
            sigaction(SIGCHLD, &action, 0) < 0) { failures++; break; }
        if (kill(getpid(), SIGUSR1) < 0 || delivered != i + 1) failures++;
        child = fork();
        if (child == (pid_t)-1) { failures++; break; }
        if (child == 0) _exit(23 + i);
        do { waited = waitpid(child, &status, 0); }
        while (waited == (pid_t)-1 && errno == EINTR);
        if (waited != child || !WIFEXITED(status) ||
            WEXITSTATUS(status) != 23 + i) failures++;
    }
    alarm(0);
    if (children != 8) failures++;
    errno = 0;
    if (waitpid((pid_t)-1, &status, WNOHANG) != (pid_t)-1 || errno != ECHILD) failures++;
    printf("delivered=%d child_notifications=%d reaped=%d\n",
           (int)delivered, (int)children, i);
    printf("RESULT failures=%d\n", failures);
    return failures ? 1 : 0;
}
