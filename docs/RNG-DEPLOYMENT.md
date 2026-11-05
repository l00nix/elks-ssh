# Ethernet-only deployment requirement

The owner clarified on 2026-11-05 that the finished service must work on ELKS
computers with Ethernet and no serial connection. SSH uses ELKS TCP/IP. Neither
the SSH client nor the server's normal operation should require a serial cable.
The existing serial adapter is a laboratory fixture, not the deployment design.

A separate decision is whether a trusted LAN helper may be required at runtime
or the service must operate independently after one-time secure provisioning.
That decision is pending; neither implementation exists. Extra RNG hardware
must not become an unstated requirement either.

## Randomness is independent of the SSH transport

A cryptographically strong generator can expand a sufficiently unpredictable
secret seed into random quantities for subsequent operations. It does not
fundamentally require fresh bytes from a companion computer for every SSH
connection. The seed and generator state must remain protected. See
[RFC 4086, sections 6 and 7.2](https://www.rfc-editor.org/rfc/rfc4086#section-6).
This is a design principle, not evidence that ELKS currently has a suitable
standalone generator and state lifecycle.

Keep the existing Dropbear protocol, authentication and crypto. The serial
experiment feeds its existing PRNG; it does not justify changing that PRNG or
putting its unauthenticated framing onto Ethernet. A different source must have
its own reviewed implementation and acceptance evidence.

## Candidate deployment models

| Model | Provisioning and operation | Main unresolved work |
| --- | --- | --- |
| Independent after setup | Provision a unique strong secret seed through trusted installation media; operate a reviewed user-space generator with protected, advancing state | Durable state advancement, forks/concurrency, failures, reboot and cloned/restored disks; 8086 code and memory cost |
| Explicit LAN-assisted mode | Provision a unique device credential; obtain fresh input over an authenticated, encrypted connection to a trusted helper | An existing suitable protocol/library, bootstrap randomness, freshness/replay state, helper outages, target footprint and credential rotation |
| Optional hardware source | Read a qualified RNG through an existing supported interface where present | Device/source qualification and availability; cannot be the only path for ordinary Ethernet-only systems |

For the independent model, prefer a published construction and existing
implementation over inventing a generator. NIST
[SP 800-90A Rev. 1](https://csrc.nist.gov/pubs/sp/800/90/a/r1/final) specifies
deterministic generators based on hash functions or block ciphers. Selecting a
construction does not solve initial seeding or storage rollback. No additional
generator has been selected or implemented here.

For an assisted model, plain TCP, an unauthenticated random-byte web service,
and a CRC do not protect the seed. A generic suggestion to "use TLS" is also
incomplete: its bootstrap entropy, authentication and replay assumptions must
be met. External PSKs require strong unique provisioning; PSK-only TLS lacks
forward secrecy, as described in
[RFC 9257 section 4.2](https://www.rfc-editor.org/rfc/rfc9257#section-4.2).
TLS is a candidate to evaluate, not an established 8086 implementation choice.

## State acceptance requirements

- No shared seed in a distributed image, static seed reused at every launch,
  clock/PID-only source, weak fallback, or private host key substituted for RNG
  state. Initial per-device provisioning must be explicit and protected.
- Advance state before releasing output, serialize consumers, and ensure
  children do not replay inherited generator output. Corruption, exhaustion or
  failed state updates must stop the affected operation.
- Test interrupted writes, process termination, reboot and exhausted storage in
  disposable QEMU images. Inspect the actual filesystem and device persistence
  semantics; successful file readback alone does not prove power-loss durability.
- Define cloned-card and restored-image recovery. A checksum cannot detect a
  valid old snapshot. Without an independent freshness source, rollback cannot
  be assumed detectable; restored/cloned media must be reprovisioned or refused.
- Keep all adaptation in user space and audit linked code for original 8086/8088.
  Measure the whole SSH session's memory, not only the generator's allocation.

The immediate work is to resolve the deployment model and test its storage or
transport prerequisites. Serial qualification is no longer the critical path.
Existing QEMU SSH, framing, native key generation and failure tests remain
useful regression evidence, but they do not establish Ethernet-only deployment.

## Storage preflight

In the prepared ELKS tree `e1469b64c5809c44d5c822eaeebd0e97d5996289`,
`elks/fs/buffer.c` implements `sys_sync()` by calling `fsync_dev(0)` and returning
zero. The latter synchronizes buffers, superblocks and inodes, including a
buffer pass with waiting enabled. This gives a user-space flush primitive but
does not report write errors through the syscall result. No per-file `fsync`
declaration is available in the inspected application headers. These findings
do not establish durable writes on every storage device or ELKS version.

Before choosing persistent state, test torn/truncated writes, failed writes,
disk-full behavior, and interruption around each update boundary. Genuine
power-loss/cache behavior needs separate qualification; a VM process reset or
file readback is not equivalent to a storage power cut.
