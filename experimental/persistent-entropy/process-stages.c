/* MIT. Diagnostic-only failure reporting; preserve syscall results/errno.
 * No command arguments, environment, keys or buffers are printed.
 */
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

pid_t elkssh_trace_fork(void)
{
    pid_t result;
    int saved;
    fprintf(stderr, "PROCESS fork begin\n"); fflush(stderr);
    result = fork();
    saved = errno;
    /* ELKS pid_t is unsigned; its failure sentinel is (pid_t)-1. */
    if (result == (pid_t)-1) fprintf(stderr, "PROCESS fork failed errno=%d\n", saved);
    fflush(stderr);
    errno = saved;
    return result;
}

int elkssh_trace_pipe(int fds[2])
{
    int result = pipe(fds);
    int saved = errno;
    if (result != 0) fprintf(stderr, "PROCESS pipe failed result=%d errno=%d\n", result, saved);
    fflush(stderr);
    errno = saved;
    return result;
}

int elkssh_trace_execv(const char *path, char *const argv[])
{
    int result = execv(path, argv);
    int saved = errno;
    if (result < 0) fprintf(stderr, "PROCESS execv failed errno=%d\n", saved);
    fflush(stderr);
    errno = saved;
    return result;
}
