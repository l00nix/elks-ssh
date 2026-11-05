/* MIT. Experimental assisted entropy; trusted physical cable only. */
#ifndef ELKSSH_SERIAL_ENTROPY_H
#define ELKSSH_SERIAL_ENTROPY_H
#include <sys/types.h>
ssize_t elkssh_serial_getrandom(void *, size_t, unsigned int);
#endif
