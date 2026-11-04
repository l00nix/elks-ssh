/* MIT. Application code placement for the unchanged, pinned BearSSL source.
 * The stock ELKS medium linker script maps .fartext into its second segment.
 * far_section is essential: section alone can leave same-segment calls behind.
 * This changes placement/call generation, not the arithmetic or public API. */
#include <stdint.h>
static void f255_mulgen(uint32_t *, const uint32_t *, const uint32_t *, int)
    __attribute__((far_section, section(".fartext.m15")));
