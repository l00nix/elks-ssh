/* MIT. Host-only experimental provisioning helper, not an ELKS binary.
 * Input: exactly 48 secret bytes from a trusted host OS through a pipe.
 * Output: one secret 1024-byte state record, never diagnostic hex output.
 * Generator implementation is unchanged pinned BearSSL 0.6.
 */
#include <stdio.h>
#include <string.h>
#include "bearssl.h"

static void wipe(void *ptr, size_t size)
{
    volatile unsigned char *p = ptr;
    while (size--) *p++ = 0;
}

int main(void)
{
    unsigned char seed[48], record[1024];
    br_hmac_drbg_context ctx;
    br_sha256_context hash;
    int result = 1;
    memset(&ctx, 0, sizeof ctx);
    memset(&hash, 0, sizeof hash);
    memset(record, 0, sizeof record);
    if (fread(seed, 1, sizeof seed, stdin) != sizeof seed
        || fgetc(stdin) != EOF || ferror(stdin)) goto done;
    br_hmac_drbg_init(&ctx, &br_sha256_vtable, seed, sizeof seed);
    memcpy(record, "ESHRNG01", 8);
    memcpy(record + 12, ctx.K, 32);
    memcpy(record + 44, ctx.V, 32);
    br_sha256_init(&hash);
    br_sha256_update(&hash, record, 992);
    br_sha256_out(&hash, record + 992);
    if (fwrite(record, 1, sizeof record, stdout) == sizeof record
        && fflush(stdout) == 0) result = 0;
done:
    wipe(seed, sizeof seed);
    wipe(record, sizeof record);
    wipe(&ctx, sizeof ctx);
    wipe(&hash, sizeof hash);
    return result;
}
