/* MIT. Experimental only: keep Dropbear's source retry interface separate
 * from the strict persistent-consumer API. There is no entropy-collection
 * wait; disk I/O may block. Lock contention and uncertain state fail closed.
 */
#include <errno.h>
#include "entropy.h"
#include "dropbear-source.h"

ssize_t elkssh_dropbear_getrandom(void *out, size_t size, unsigned int flags)
{
    /* Dropbear tries GRND_NONBLOCK (1) before a zero-flags retry. */
    if (flags & ~1U) {
        errno = EINVAL;
        return -1;
    }
    return elkssh_persistent_getrandom(out, size, 0);
}
