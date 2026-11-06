/* MIT. Application-only code placement using the stock ELKS linker script.
 * Move the unchanged SHA-256 round function into the first code segment to
 * balance the isolated m15 diagnostic build. Keep far calling conventions.
 * No installed libc, linker script, kernel or arithmetic is modified.
 */
#include <stdint.h>
void br_sha2small_round(const unsigned char *, uint32_t *)
    __attribute__((far_section, section(".text.rnground")));
