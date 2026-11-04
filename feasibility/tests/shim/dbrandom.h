/* MIT. X25519 vectors supply their inputs; no RNG is linked into this probe. */
#ifndef ELKSSH_PROBE_RANDOM_H
#define ELKSSH_PROBE_RANDOM_H
#if DROPBEAR_ED25519
#error This test configuration must not enable key generation
#endif
#endif
