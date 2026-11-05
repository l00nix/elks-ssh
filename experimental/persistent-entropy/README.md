# Persistent state experiment

**Not a deployment-ready RNG. Do not install as an SSH randomness source.**
This is the next experiment for independent operation after trusted one-time
provisioning. It uses unchanged BearSSL HMAC_DRBG/SHA-256. The public fixture
is deliberately predictable and must never provision a real service.

## Design comparison

| Storage approach | Effect on ELKS | Experimental choice |
| --- | --- | --- |
| Temporary file plus rename on every request | Requires allocations and durable file/directory metadata ordering; more disk-full and recovery cases | Defer |
| Two slots with automatic fallback | Can recover availability, but selecting an older valid slot may repeat already exposed output | Reject automatic fallback |
| One preallocated block, exclusive lock, checksum and readback | Bounds memory and avoids reallocating state; any damaged state or abandoned lock requires operator recovery | Evaluate first |
| Resident RNG service | Additional process/memory and IPC protocol; still requires durable reboot state | Defer |

Each request obtains an exclusive lock file, loads and validates the state,
generates exactly 32 bytes, saves the advanced state, calls `sync()`, and checks
the complete record by reopening it. Only then may it remove its lock and
return bytes. There is no retained generator context between requests: forked
processes must acquire the same lock and load the advanced state. Contention
fails closed rather than waiting indefinitely. Errors poison that process's
adapter; after acquiring the lock, errors leave it in place for recovery.

The record is 1,024 bytes: eight-byte version/magic, a four-byte big-endian
generation count, SHA-256 HMAC_DRBG K and V (32 bytes each), zero padding, and
a trailing SHA-256 checksum of the first 992 bytes. This checksum detects
accidental corruption, not malicious rollback. State and lock live in a private
root-owned directory on a filesystem that enforces permissions. The generation
limit is 1,048,576 requests per provisioning; the adapter will refuse exhaustion.
Persisting state does not count as obtaining new entropy or reseeding the DRBG.

## Unresolved release conditions

`sync()` does not return disk errors on the inspected ELKS build. The separate
storage probe shows that readback detects injected reported errors on that
specific QEMU BIOS/MINIX path, including a partially written block. It cannot
detect a device that acknowledges writes held only in volatile storage. Thus
this adapter assumes a qualified write-through/durable-write storage path;
readback alone does not establish that assumption. QEMU uses write-through
storage for the experiment. Physical power-loss behavior is still unqualified.

An old but valid state restored from backup, a cloned card, or a VM snapshot
can repeat output. Such media must be securely reprovisioned before SSH use;
no checksum or local-only counter detects arbitrary rollback. Stolen state
also requires fresh secret provisioning. No automatic lock removal, fallback
to older state, timing-only entropy, or host-key-derived seed is permitted.

The production provisioning/recovery utility, complete SSH integration,
whole-session memory measurements, real 8086 execution and physical storage
qualification are not supplied by this probe. No kernel/libc changes are made.

Recorded results and remaining hardware gates: [persistent-state checkpoint](../../docs/PERSISTENT-STATE.md).
