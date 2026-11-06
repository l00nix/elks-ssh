# Ed25519 comparison tests

All fixtures are public, deterministic test data. They are never installed as
runtime credentials. `fixtures.py` uses the pinned Wycheproof verification
corpus and Python cryptography's independent Ed25519 implementation. It produces
646 host cases, 175 representative ELKS cases, and a seven-case hardware probe.

The adapter requires canonical encodings and rejects small-order points. It
uses the upstream uncofactored verification equation, not a full prime-subgroup
membership test. Wycheproof's 21 mixed-order-key cases are marked acceptable by
the corpus: their acceptance is recorded rather than forced to either result.
Its eight small-order-key acceptable cases must be rejected by our policy.
All valid cases must pass and all invalid cases must fail.

The additional fixtures cover deterministic signing and independent verification,
SHA-512 prefix/block boundaries, altered R, S+L malleability, short signatures,
identity-key forgeries and oversized-message refusal before dereferencing NULL.
The 4096-byte message limit protects unchanged upstream size_t arithmetic on
16-bit ELKS; it exceeds the experimental server's 2048-byte transmit payload.

`check.c` reads bounded records from a fixture file. It is not an authentication
program. `qemu.py` uses a disposable FAT image without a NIC and verifies fixture
results, process cleanup and preservation of the original image. The probe heap
is 4 KiB because buffered file I/O needs more than the original 1 KiB allocation.
That test-harness correction does not change the SSH worker's heap reservation.

The linked probe can reuse the server's exact crypto object files by setting
`ELKSSH_EDPROBE_OBJECTS` when invoking `build-probe.sh`. Source-level correctness
and a static ISA audit do not establish constant-time execution on every CPU.
