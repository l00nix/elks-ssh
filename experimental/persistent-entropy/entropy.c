/* MIT. Experimental only; requires a separately qualified durable storage path.
 * No initial seed, provisioning, automatic recovery, or fallback is provided.
 */
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include "bearssl.h"
#include "entropy.h"
#ifndef ELKSSH_RNG_DIR
#define ELKSSH_RNG_DIR "/root/rngtest"
#endif
#define STATE ELKSSH_RNG_DIR "/state"
#define LOCK ELKSSH_RNG_DIR "/lock"
#define LIMIT UINT32_C(1048576)
static int poisoned;

#ifdef ELKSSH_RNG_TEST_HOOKS
void elkssh_rng_stage(unsigned int stage);
#define STAGE(n) elkssh_rng_stage(n)
#else
#define STAGE(n) ((void)0)
#endif

static void wipe(void *ptr, unsigned int size)
{
    volatile unsigned char *p = ptr;
    while (size--) *p++ = 0;
}

static int protected_path(const char *path, int directory, struct stat *st)
{
    return lstat(path, st) == 0 && st->st_uid == 0
        && (st->st_mode & 077) == 0
        && (directory ? S_ISDIR(st->st_mode)
                      : S_ISREG(st->st_mode) && st->st_nlink == 1 && st->st_size == 1024);
}

static int state_open(void)
{
    struct stat before, after;
    int fd;
    if (!protected_path(STATE, 0, &before)) return -1;
    fd = open(STATE, O_RDWR);
    if (fd < 0) return -1;
    if (fstat(fd, &after) < 0 || after.st_dev != before.st_dev
        || after.st_ino != before.st_ino || after.st_size != 1024
        || after.st_uid != 0 || (after.st_mode & 077) || after.st_nlink != 1
        || !S_ISREG(after.st_mode)) {
        close(fd); return -1;
    }
    return fd;
}

static void digest(const unsigned char *record, unsigned char *hash)
{
    br_sha256_context h;
    br_sha256_init(&h);
    br_sha256_update(&h, record, 992);
    br_sha256_out(&h, hash);
    wipe(&h, sizeof h);
}

ssize_t elkssh_persistent_getrandom(void *out, size_t size, unsigned int flags)
{
    unsigned char record[1024], verify[1024], bytes[32], hash[32];
    br_hmac_drbg_context ctx;
    struct stat st;
    uint32_t generation;
    unsigned int i;
    int fd = -1, lock = -1;
    if (poisoned || size != 32 || flags || geteuid() != 0) {
        errno = EIO; return -1;
    }
    if (!protected_path(ELKSSH_RNG_DIR, 1, &st)) goto fail;
    lock = open(LOCK, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (lock < 0) goto fail;
    if (close(lock) < 0) { lock = -1; goto fail; }
    lock = -1;
    sync();
    STAGE(1);
    fd = state_open();
    if (fd < 0 || read(fd, record, sizeof record) != sizeof record) goto fail;
    digest(record, hash);
    if (memcmp(record, "ESHRNG01", 8) || memcmp(hash, record+992, 32)) goto fail;
    for (i = 76; i < 992; i++) if (record[i]) goto fail;
    generation = ((uint32_t)record[8]<<24) | ((uint32_t)record[9]<<16)
        | ((uint32_t)record[10]<<8) | record[11];
    if (generation >= LIMIT) goto fail;
    /* Restore only algorithm fields, never persisted pointers or host layout. */
    memset(&ctx, 0, sizeof ctx);
    ctx.vtable = &br_hmac_drbg_vtable;
    ctx.digest_class = &br_sha256_vtable;
    memcpy(ctx.K, record+12, 32);
    memcpy(ctx.V, record+44, 32);
    br_hmac_drbg_generate(&ctx, bytes, sizeof bytes);
    generation++;
    record[8] = generation>>24; record[9] = generation>>16;
    record[10] = generation>>8; record[11] = generation;
    memcpy(record+12, ctx.K, 32);
    memcpy(record+44, ctx.V, 32);
    digest(record, record+992);
    STAGE(2);
    if (lseek(fd, 0, SEEK_SET) != 0 || write(fd, record, sizeof record) != sizeof record) goto fail;
    if (close(fd) < 0) { fd = -1; goto fail; }
    fd = -1;
    STAGE(3);
    sync();
    STAGE(4);
    fd = state_open();
    if (fd < 0 || read(fd, verify, sizeof verify) != sizeof verify
        || memcmp(record, verify, sizeof record)) goto fail;
    if (close(fd) < 0) { fd = -1; goto fail; }
    fd = -1;
    STAGE(5);
    if (unlink(LOCK) < 0) goto fail;
    sync();
    STAGE(6);
    memcpy(out, bytes, sizeof bytes);
    wipe(&ctx, sizeof ctx); wipe(record, sizeof record);
    wipe(verify, sizeof verify); wipe(bytes, sizeof bytes); wipe(hash, sizeof hash);
    return 32;
fail:
    poisoned = 1;
    if (fd >= 0) close(fd);
    if (lock >= 0) close(lock);
    /* Leave any acquired lock. Do not silently retry uncertain state. */
    wipe(&ctx, sizeof ctx); wipe(record, sizeof record);
    wipe(verify, sizeof verify); wipe(bytes, sizeof bytes); wipe(hash, sizeof hash);
    errno = EIO;
    return -1;
}
