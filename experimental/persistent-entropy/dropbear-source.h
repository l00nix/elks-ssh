/* MIT. Experimental Dropbear source adapter; no kernel/libc API change. */
#ifndef ELKSSH_DROPBEAR_PERSISTENT_SOURCE_H
#define ELKSSH_DROPBEAR_PERSISTENT_SOURCE_H
#include <sys/types.h>
ssize_t elkssh_dropbear_getrandom(void *, size_t, unsigned int);
#endif
