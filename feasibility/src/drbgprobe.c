/* MIT. Public known-answer probe only; never supplies entropy to SSH.
 * Vectors: BearSSL 0.6 test/test_crypto.c, test_HMAC_DRBG (Thomas Pornin).
 * See feasibility/vendor/bearssl/LICENSE.txt and manifest.json.
 */
#include <stdio.h>
#include <string.h>
#include "bearssl.h"

static const char seed_hex[] =
    "009A4D6792295A7F730FC3F2B49CBC0F62E862272F"
    "01795EDF0D54DB760F156D0DAC04C0322B3A204224";
static const char *refs[] = {
    "9305A46DE7FF8EB107194DEBD3FD48AA20D5E7656CBE0EA69D2A8D4E7C67",
    "C70C78608A3B5BE9289BE90EF6E81A9E2C1516D5751D2F75F50033E45F73",
    "475E80E992140567FCC3A50DAB90FE84BCD7BB03638E9C4656A06F37F650"
};

static unsigned int digit(char c)
{
    return c <= '9' ? (unsigned int)(c - '0') : (unsigned int)(c - 'A' + 10);
}

static void decode(unsigned char *out, const char *hex, unsigned int n)
{
    unsigned int i;
    for (i = 0; i < n; i++)
        out[i] = (unsigned char)((digit(hex[2*i]) << 4) | digit(hex[2*i+1]));
}

int main(void)
{
    br_hmac_drbg_context ctx, copy;
    unsigned char seed[42], out[30], ref[30];
    unsigned int api, i, checks = 0;
    printf("HMAC_DRBG public vectors; context=%u bytes\n", (unsigned int)sizeof ctx);
    decode(seed, seed_hex, sizeof seed);
    for (api = 0; api < 2; api++) {
        memset(&ctx, 0, sizeof ctx);
        if (api == 0)
            br_hmac_drbg_init(&ctx, &br_sha256_vtable, seed, sizeof seed);
        else
            br_hmac_drbg_vtable.init(&ctx.vtable, &br_sha256_vtable, seed, sizeof seed);
        for (i = 0; i < 3; i++) {
            if (api == 0) br_hmac_drbg_generate(&ctx, out, sizeof out);
            else ctx.vtable->generate(&ctx.vtable, out, sizeof out);
            decode(ref, refs[i], sizeof ref);
            if (memcmp(out, ref, sizeof out)) {
                printf("FAIL api=%u vector=%u\n", api, i);
                return 1;
            }
            checks++;
        }
    }
    /* Demonstrate why a forked or restored context needs lifecycle handling. */
    memcpy(&copy, &ctx, sizeof copy);
    br_hmac_drbg_generate(&ctx, out, sizeof out);
    br_hmac_drbg_generate(&copy, ref, sizeof ref);
    if (memcmp(out, ref, sizeof out)) return 1;
    puts("OBSERVATION copied state repeats output; persistence/fork safety untested");
    printf("RESULT PASS checks=%u failures=0\n", checks);
    return 0;
}
