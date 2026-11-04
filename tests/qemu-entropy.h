/* MIT. Test-only getrandom transport; never part of a normal ELKS build. */
#ifndef ELKSSH_QEMU_ENTROPY_H
#define ELKSSH_QEMU_ENTROPY_H
#include <sys/types.h>
ssize_t elkssh_qemu_getrandom(void *buffer, size_t size, unsigned int flags);
#endif
