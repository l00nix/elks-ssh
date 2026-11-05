# Ethernet-only deployment requirement

The owner clarified on 2026-11-05 that the finished service must work on ELKS
computers with Ethernet and no serial connection. SSH uses ELKS TCP/IP. Neither
the SSH client nor the server's normal operation should require a serial cable.
The existing serial adapter is a laboratory fixture, not the deployment design.

**Decision confirmed by the owner:** the service must operate independently
after one-time secure provisioning. A LAN helper, companion host, serial cable
or extra RNG hardware must not be required at runtime. The standalone
implementation is not yet available. The HP tests did not implement it: see
[HP progress](HP200LX-PROGRESS.md) for crypto probes and the missing-randomness
startup refusal.

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

## Deployment comparison and decision

| Model | Provisioning and operation | Main unresolved work |
| --- | --- | --- |
| **Selected: independent after setup** | Provision a unique strong secret seed through trusted installation media; operate a reviewed user-space generator with protected, advancing state | Durable state advancement, forks/concurrency, failures, reboot and cloned/restored disks; 8086 code and memory cost |
| Rejected as required deployment: LAN-assisted mode | Provision a unique device credential; obtain fresh input over an authenticated, encrypted connection to a trusted helper | An existing suitable protocol/library, bootstrap randomness, freshness/replay state, helper outages, target footprint and credential rotation |
| Optional hardware source | Read a qualified RNG through an existing supported interface where present | Device/source qualification and availability; cannot be the only path for ordinary Ethernet-only systems |

For the independent model, prefer a published construction and existing
implementation over inventing a generator. NIST
[SP 800-90A Rev. 1](https://csrc.nist.gov/pubs/sp/800/90/a/r1/final) specifies
deterministic generators based on hash functions or block ciphers. Selecting a
construction does not solve initial seeding or storage rollback. No additional
production generator has been selected or integrated here.

### Generator implementation comparison

| Candidate | Whole-system effect | Decision for the next experiment |
| --- | --- | --- |
| Persist the existing Dropbear hash pool directly | Reuses linked SHA-256; couples storage, fork handling and secret state to protocol internals; upstream still expects external seeding | Preserve upstream behavior; do not turn its internal pool into a new persistent RNG construction |
| BearSSL 0.6 HMAC_DRBG with SHA-256 | Existing MIT implementation of a published construction; small fixed context, no heap requirement in the generator; adds HMAC/SHA code unless later reuse is justified | Measure unchanged upstream code in a separate public-vector probe first |
| A new generator based on existing ChaCha20 | Might reuse cipher code, but adds a new state/reseed construction and review burden | Do not design a new generator |

The BearSSL probe selects an implementation to evaluate, not a production
architecture. It does not persist state, provision a machine, or feed SSH.
[BearSSL documents](https://bearssl.org/apidoc/bearssl__rand_8h.html) that its
HMAC_DRBG API does not enforce request/reseed limits: a production adapter
would need to bound requests and generator lifetime explicitly. Copying its
context after fork repeats output unless the caller separates state. No
software generator can recover unpredictability after its full secret state
is stolen without new secret input; reprovisioning is required in that case.

A LAN entropy protocol is out of the critical path and would not satisfy the
selected deployment requirement. The laboratory serial framing must not be
repurposed as an unauthenticated network source.

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

The immediate work is to compare existing generator implementations and test
the selected model's storage prerequisites. Serial qualification is no longer the critical path.
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

## First independent-generator probe — 2026-11-05

The isolated `drbgprobe` uses unchanged BearSSL 0.6 HMAC_DRBG, HMAC and SHA-256
sources from the pinned archive. All six upstream known-answer checks pass
on the Mac and in a disposable ELKS QEMU 486 fixture. The probe also demonstrates
that copying the generator context repeats output; it supplies no SSH randomness.

- ELKS context: 132 bytes. Probe linked code: 10,416 bytes including runtime.
- Probe near-memory reservation: 9,152 bytes before arguments/environment,
  including 1,024-byte heap and 4,096-byte stack. These are probe reservations,
  not the incremental cost or peak consumption of a complete SSH session.
- Linked original-8086 static instruction audit: pass. Physical 8086/8088
  execution, arithmetic timing and production integration are not tested.
- Input FAT image remains unchanged; QEMU had no network device. No hardware
  was accessed and no runtime seed or host key was created.

Evidence: [QEMU result](evidence/20261105-standalone-rng/qemu-result.json),
[transcript](evidence/20261105-standalone-rng/qemu-serial.txt),
[linked audit](evidence/20261105-standalone-rng/drbgprobe-audit.json), and
[source hashes](evidence/20261105-standalone-rng/sources.json).

Reproduce from the repository root:

```sh
ELKSSH_ELKS=/path/to/prepared/elks sh feasibility/toolchain/build-drbg.sh
python3 feasibility/tests/qemu_crypto_integration.py \
  --image /path/to/hd32-fat.img --build feasibility/build/drbg \
  --names drbgprobe --out feasibility/test-output/drbg-qemu
```

Next gate: a separately tested persistent-state lifecycle and storage contract.
The inspected ELKS headers expose neither `O_SYNC` nor `O_DIRECT`, and the
inspected block-device file operations use the buffer cache. Reopening and
reading a file is therefore not evidence of media persistence. `sync()` returns
zero after its global flush, without reporting a failed device write. These
source findings need to inform the fault-injection fixture; the generator probe
must not be turned into a deployable seed-file adapter on the strength of its
known-answer tests. No daemon, key tool or machine startup configuration changed.
