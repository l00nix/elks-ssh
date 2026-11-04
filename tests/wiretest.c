/* MIT. Public regression vectors; no networking, RNG or authentication. */
#include "includes.h"
#include "buffer.h"
#include "dbutil.h"
#include "session.h"
#include "chachapoly.h"

static jmp_buf failure;
static int expecting_failure, failures, checks;

/* Test-only failure interception. Production exit and comparison code is not
 * linked here; buffer, allocator, ChaCha20 and Poly1305 are production sources. */
void dropbear_exit(const char *format, ...) {
    if (expecting_failure) longjmp(failure, 1);
    fprintf(stderr, "Unexpected fatal: %s\n", format);
    exit(2);
}
int constant_time_memcmp(const void *a, const void *b, size_t n) {
    return memcmp(a, b, n);
}
void m_burn(void *data, unsigned int len) {
    memset(data, 0, len);
}

static void check(int pass, const char *name) {
    printf("%s %s\n", pass ? "PASS" : "FAIL", name);
    checks++;
    if (!pass) failures++;
}
#define REJECT(expr, name) do { \
    expecting_failure = 1; \
    if (setjmp(failure) == 0) { (void)(expr); check(0, name); } \
    else { check(1, name); } \
    expecting_failure = 0; \
} while (0)

static void buffers(void) {
    static const uint32_t values[] = {0, 65535UL, 65536UL, 2097152UL, 0xffffffffUL};
    unsigned int i;
    buffer *b = buf_new(32);
    unsigned char data[8] = {0};
    buffer large = {data, 60010U, 60000U, 60010U};
    for (i=0; i<sizeof(values)/sizeof(values[0]); i++) buf_putint(b, values[i]);
    buf_setpos(b, 0);
    for (i=0; i<sizeof(values)/sizeof(values[0]); i++) {
        if (buf_getuint32(b) != values[i]) break;
    }
    check(i == sizeof(values)/sizeof(values[0]), "SSH uint32 roundtrip through 0xffffffff");
    buf_setpos(b, 8);
#if UINT_MAX == 65535U
    REJECT(buf_getint(b), "65536 rejected as local memory size");
#endif
    buf_setpos(b, 0);
    buf_putint(b, 0x00010001UL);
    buf_setpos(b, 0);
    REJECT(buf_getstring(b, NULL), "oversized wire string rejected before narrowing");
    REJECT(buf_getptr(&large, 10000U), "read span cannot wrap");
    REJECT(buf_getwriteptr(&large, 10000U), "write span cannot wrap");
    REJECT(buf_incrpos(&large, 10000U), "position cannot wrap");
    REJECT(buf_incrwritepos(&large, 10000U), "write position cannot wrap");
    REJECT(buf_incrlen(&large, 10000U), "length cannot wrap");
    REJECT(buf_new(UINT_MAX), "allocation includes buffer header without wrap");
    REJECT(buf_resize(b, UINT_MAX), "resize includes buffer header without wrap");
    REJECT(m_calloc((size_t)-1, 2), "calloc product cannot wrap");
    REJECT(m_calloc(0, 2), "zero calloc fails without dividing by zero");
    buf_free(b);
}

static void cipher(void) {
    static const unsigned char key[64] = {0};
    static const unsigned char plain[16] = {0,0,0,12, 8,1,2,3,4,5,6,7,8,9,10,11};
    static const uint32_t sequences[] = {0, 65535UL, 65536UL, 0xffffffffUL};
    unsigned char encrypted[32], first[32], decoded[16];
    dropbear_chachapoly_state state;
    const struct dropbear_cipher_mode *mode = &dropbear_mode_chachapoly;
    unsigned int i, length;
    int rc, ok = 1;
    uint32_t seq = 65535UL;
    seq++;
    check(sizeof(((struct sshsession*)0)->transseq) == 4 && seq == 65536UL &&
          sizeof(((struct sshsession*)0)->kexstate.datatrans) == 4 &&
          sizeof(((struct sshsession*)0)->kexstate.datarecv) == 4,
          "sequence and rekey counters remain 32 bits");
    for (i=0; i<4; i++) {
        rc = mode->start(0, NULL, key, sizeof(key), 0, &state);
        rc |= mode->aead_crypt(sequences[i], plain, encrypted, sizeof(plain), 16, &state, LTC_ENCRYPT);
        if (rc != CRYPT_OK) ok = 0;
        if (i == 0) memcpy(first, encrypted, sizeof(first));
        if (i == 2) check(memcmp(first, encrypted, sizeof(first)) != 0,
                          "nonce differs at packet 0 and 65536");
        rc = mode->aead_getlength(sequences[i], encrypted, &length, 4, &state);
        if (rc != CRYPT_OK || length != 12) ok = 0;
        rc = mode->aead_crypt(sequences[i], encrypted, decoded, 16, 16, &state, LTC_DECRYPT);
        if (rc != CRYPT_OK || memcmp(decoded, plain, sizeof(plain))) ok = 0;
        /* Independent host-generated expected ciphertexts are compared by
         * the QEMU harness, including the encrypted header and Poly1305 tag. */
        printf("VECTOR %lu ", (unsigned long)sequences[i]);
        { unsigned int j; for (j=0; j<32; j++) printf("%02x", encrypted[j]); }
        printf("\n");
        encrypted[31] ^= 1;
        rc = mode->aead_crypt(sequences[i], encrypted, decoded, 16, 16, &state, LTC_DECRYPT);
        if (rc == CRYPT_OK) ok = 0;
    }
    check(ok, "ChaChaPoly lengths roundtrips and tamper rejection across 16-bit boundary");
}

int main(void) {
    printf("ELKS SSH wire regression int=%u pointer=%u\n", (unsigned)sizeof(int), (unsigned)sizeof(void*));
    buffers();
    cipher();
    printf("RESULT %s checks=%d failures=%d\n", failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
