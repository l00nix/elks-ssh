/* MIT. Public known-answer tests only. This is not an SSH service. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include "curve25519.h"
#include "crypto_hash_sha256.h"
#include "crypto_stream_chacha20.h"

typedef char need_u32[sizeof(uint32_t) == 4 ? 1 : -1];
typedef char need_i64[sizeof(long long) == 8 ? 1 : -1];

static int failures;

static unsigned char nibble(char c)
{
	return c <= '9' ? c - '0' : c - 'a' + 10;
}

/* Only called with the fixed, reviewed hexadecimal literals below. */
static void unhex(unsigned char *out, const char *text)
{
	while (*text) {
		*out++ = (nibble(text[0]) << 4) | nibble(text[1]);
		text += 2;
	}
}

static void check(const char *name, const unsigned char *got,
		  const char *expected, unsigned int len)
{
	unsigned char want[64];
	unhex(want, expected);
	if (memcmp(got, want, len)) {
		printf("FAIL %s\n", name);
		failures++;
	} else {
		printf("PASS %s\n", name);
	}
	fflush(stdout);
}

static void x25519_tests(void)
{
	unsigned char alice[32], bob[32], ap[32], bp[32], out[32];
	unsigned char base[32] = {9};
	unsigned char zero[32] = {0};

	/* RFC 7748 section 6.1, Alice/Bob example. These are NOT secret keys. */
	unhex(alice, "77076d0a7318a57d3c16c17251b26645"
		     "df4c2f87ebc0992ab177fba51db92c2a");
	unhex(bob, "5dab087e624a8a4b79e17f8b83800ee6"
		   "6f3bb1292618b6fd1c2f8b27ff88e0eb");
	dropbear_curve25519_scalarmult(ap, alice, base);
	check("X25519 Alice public", ap,
	      "8520f0098930a754748b7ddcb43ef75a"
	      "0dbf3a0d26381af4eba4a98eaa9b4e6a", 32);
	dropbear_curve25519_scalarmult(bp, bob, base);
	check("X25519 Bob public", bp,
	      "de9edb7d7b7dc1b4d35b61c2ece43537"
	      "3f8343c85b78674dadfc7e146f882b4f", 32);
	dropbear_curve25519_scalarmult(out, alice, bp);
	check("X25519 Alice shared", out,
	      "4a5d9d5ba4ce2de1728e3bf480350f25"
	      "e07e21c947d19e3376f09b3c1e161742", 32);
	dropbear_curve25519_scalarmult(out, bob, ap);
	check("X25519 Bob shared", out,
	      "4a5d9d5ba4ce2de1728e3bf480350f25"
	      "e07e21c947d19e3376f09b3c1e161742", 32);
	/* The primitive returns zero; a future SSH caller must reject it. */
	dropbear_curve25519_scalarmult(out, alice, zero);
	check("X25519 low-order result (must reject in SSH)", out,
	      "00000000000000000000000000000000"
	      "00000000000000000000000000000000", 32);
}

static void symmetric_tests(void)
{
	unsigned char out[128], plain[128], recovered[128];
	unsigned char key[32] = {0}, nonce[8] = {0};
	unsigned int i;

	crypto_hash_sha256(out, (const unsigned char *)"", 0);
	check("SHA256 empty", out,
	      "e3b0c44298fc1c149afbf4c8996fb924"
	      "27ae41e4649b934ca495991b7852b855", 32);
	crypto_hash_sha256(out, (const unsigned char *)"abc", 3);
	check("SHA256 abc", out,
	      "ba7816bf8f01cfea414140de5dae2223"
	      "b00361a396177a9cb410ff61f20015ad", 32);
	crypto_hash_sha256(out, (const unsigned char *)
		"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq", 56);
	check("SHA256 two padding blocks", out,
	      "248d6a61d20638b8e5c026930c3e6039"
	      "a33ce45964ff2167f6ecedd419db06c1", 32);
	/* Original ChaCha20: zero key, zero 64-bit nonce, counter zero. */
	crypto_stream_chacha20(out, 64, nonce, key);
	check("ChaCha20 zero block", out,
	      "76b8e0ada0f13d90405d6ae55386bd28"
	      "bdd219b8a08ded1aa836efcc8b770dc7"
	      "da41597c5157488d7724e03fb8d84a37"
	      "6a43b8f41518a11cc387b669b2ee6586", 64);
	for (i = 0; i < sizeof(plain); i++) plain[i] = i;
	crypto_stream_chacha20_xor(out, plain, sizeof(plain), nonce, key);
	crypto_stream_chacha20_xor(recovered, out, sizeof(out), nonce, key);
	if (memcmp(plain, recovered, sizeof(plain))) {
		puts("FAIL ChaCha20 multi-block roundtrip");
		failures++;
	} else puts("PASS ChaCha20 multi-block roundtrip");
}

int main(void)
{
	time_t start = time(NULL);
	puts("ELKS SSH crypto feasibility 0.0.1");
	printf("ABI int=%u long=%u pointer=%u longlong=%u\n",
	       (unsigned)sizeof(int), (unsigned)sizeof(long),
	       (unsigned)sizeof(void *), (unsigned)sizeof(long long));
	puts("Public test vectors only; no RNG, keys or listening service.");
	fflush(stdout);
	symmetric_tests();
	x25519_tests();
	printf("RESULT %s failures=%d elapsed_seconds=%ld\n",
	       failures ? "FAIL" : "PASS", failures, (long)(time(NULL) - start));
	return failures ? 1 : 0;
}
