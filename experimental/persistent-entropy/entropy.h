/* MIT. Experimental user-space persistent-state adapter. */
#ifndef ELKSSH_PERSISTENT_ENTROPY_H
#define ELKSSH_PERSISTENT_ENTROPY_H
#include <sys/types.h>
ssize_t elkssh_persistent_getrandom(void *out, size_t size, unsigned int flags);
#endif
