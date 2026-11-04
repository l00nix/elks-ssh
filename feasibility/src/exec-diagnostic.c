/* MIT. Experimental daemon diagnostics; never part of the normal build. */
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

int elkssh_probe_execv(const char *path, char *const argv[])
{
    int result = execv(path, argv);
    int saved_errno = errno;
    fprintf(stderr, "Experimental execv failed: errno=%d\n", saved_errno);
    errno = saved_errno;
    return result;
}
