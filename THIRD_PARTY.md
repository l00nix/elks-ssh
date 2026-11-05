# Third-party components

The inherited repository is ghaerr's fork of parabyte's Dropbear ELKS port,
based on Dropbear 2025.89. Its original history and root LICENSE are retained.
Our starting commit is `2bee5b852fa3789a8f5539a20291020d53eea427`.

The files in `feasibility/vendor/` are unmodified copies for independent probes and isolated experimental builds.
Their paths, pinned upstream commits or release archives and SHA-256 hashes are recorded in
[manifest.json](feasibility/vendor/manifest.json).

- **Dropbear**: `src/curve25519.c`, `src/curve25519.h`, and license from
  [mkj/dropbear](https://github.com/mkj/dropbear/tree/17549ea6b6be0d59e99c5c5350185c0f9cc57211).
  The source contains Matt Johnston's permissive notice and identifies its
  modified public-domain TweetNaCl origin. The initial build enables X25519
  only; the included source's Ed25519 portion is not yet built.
- **TinySSH**: SHA-256, ChaCha20, headers and cryptoint headers from
  [janmojzis/tinyssh](https://github.com/janmojzis/tinyssh/tree/6a60c2aac18da9035a7401316789d6f4df7e295f).
  See its retained `LICENSE.md` and `cryptoint/README` for the upstream license
  choices and Daniel J. Bernstein attribution.
- **BearSSL 0.6**: unchanged m15, HMAC_DRBG, HMAC, SHA-256, codec sources and build headers
  from the [official release archive](https://bearssl.org/bearssl-0.6.tar.gz).
  Thomas Pornin's MIT license is retained in `feasibility/vendor/bearssl/LICENSE.txt`.
  Comparative X25519 probes and the isolated `dropbear-m15` experiment link
  the m15 subset. The isolated `drbgprobe` links the HMAC_DRBG subset; its
  six known-answer checks use the public `test_HMAC_DRBG` vectors from the
  same pinned archive. The normal daemon does not link BearSSL.
- **ELKSWeb audit tools**: `feasibility/tools/isa-audit.py` and `test_isa_audit.py`
  copied from l00nix/ELKSWeb commit `399c79b6ef34806f2ed65bfcc976452ee687d5a8`
  on 2026-11-04, GPL-2.0; license in `feasibility/tools/COPYING`.
  These are build-analysis programs, not linked into the probe executable.

The shim headers under `feasibility/tests/shim/` select upstream crypto features for a
standalone feasibility test. They are not a substitute for a complete Dropbear
configuration or port. Fixed RFC test vectors are public test data, never keys
for a running service.

New production-code regression harnesses in `tests/` use [tests/LICENSE](tests/LICENSE).
The independent vector generator uses the host Python `cryptography` package
(50.0.2 for recorded vectors); that package is not vendored or linked into ELKS.
