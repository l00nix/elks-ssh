# Assisted serial entropy checkpoint — 2026-11-05

A separate experimental Dropbear build can obtain fresh seeds from the Mac OS
random source over a dedicated, physically trusted serial cable. It runs above
existing ELKS APIs, without kernel, libc or firmware changes. The PPC has
Ethernet for test control; the HP remains on its serial console with networking
stopped. This is not a release candidate, standalone RNG, or hardware SSH login.

The new adapter is isolated under
[experimental/serial-entropy](../experimental/serial-entropy/README.md).
It replaces neither Dropbear's crypto nor its PRNG. A public one-use session ID
and shared request counter bind responses across forks. Strict framing, a
corruption checksum, protected state/device permissions and bounded I/O reject
invalid input. The checksum is **not authentication**: the physically controlled
cable and trusted endpoints are the security boundary. Never use this protocol
as an unauthenticated network entropy relay.

## Recorded results

| Test | Result |
| --- | --- |
| Host protocol unit tests | 6 pass |
| QEMU probe matrix | 70 pass, including all truncated frames of 0–59 bytes |
| QEMU daemon startup matrix | 12 pass; no seed-file fallback/writeback |
| Physical PPC probe matrix | 10 pass |
| Physical PPC daemon startup | Fresh seed accepted, deliberately absent host key rejected |
| Relaunch without fresh bootstrap | Refused on emulator and PPC |
| Linked original-8086/no-FPU static audits | Both probe and daemon variants pass |
| Ordinary daemon rebuilt after guarded changes | SHA-256 identical to baseline |

The probe covers parent/child requests, stale session and counter values,
replayed responses, corruption, timeouts, short input, unsafe device permissions
and an occupied port. Failure preserves the caller's buffer and prevents retry
from accepting delayed bytes. The successful PPC probe consumed four distinct
seeds in 2.642 seconds; silent/short-input failures took about 10–11.4 seconds.
These are entropy-probe times, not SSH handshake measurements.

The final PPC daemon consumed one seed and exited with `No hostkeys available`
using the deliberately missing `/root/no-key`. Its next launch exited with
`Failure reading dedicated serial entropy`. Both exited 1. `ps` and `netstat`
showed no remaining SSH daemon/listener. Device permissions were restored and
the provider stopped. No SSH host/client private keys were provisioned.

Evidence: [QEMU probe matrix](evidence/20261105-serial-entropy/qemu-probe-matrix.json),
[QEMU daemon matrix](evidence/20261105-serial-entropy/qemu-daemon-matrix.json),
[PPC probe matrix](evidence/20261105-serial-entropy/ppc-probe-matrix.json),
[PPC daemon transcript](evidence/20261105-serial-entropy/ppc-daemon.txt),
[provider counts](evidence/20261105-serial-entropy/ppc-provider.txt).
Logs contain no seed bytes or private keys. Guest wall-clock dates are unset;
the checkpoint date is the host test date.

## Build identity

Prepared ELKS tree: `e1469b64c5809c44d5c822eaeebd0e97d5996289` with IA16 GCC
6.3.0, `-march=i8086 -mtune=i8086`. Physical target: vanilla ELKS 0.9.2
`e7a56a43` on the PPC. Binary transfer was verified by readback.

| Binary | SHA-256 |
| --- | --- |
| PPC probe | `b265b0b92736ca01e1404e6366a391e5e57622688c7d7521e51c30f73a06eb40` |
| PPC experimental daemon | `862d8d6708ce6a003c98948ff019c43ce309e1ea389f2e5c4f8c91eb8f2dfa9a` |
| Unchanged ordinary daemon | `6613bdd3e73c1502d8ee45f0dc18b1cdb1b0a87a58147a528cb008eaa4abdabb` |

[Source hashes](evidence/20261105-serial-entropy/source-sha256.json) identify the
adaptation and harnesses. The evidence directory also retains all four linked
ISA audits. Static instruction compatibility does not establish execution on
every 8086/8088 machine or ELKS version. This experiment uses the normal crypto
backend; it does not resolve the [m15 memory/timing issues](M15-DAEMON.md).

## Remaining qualification

Physical USB disconnect/reconnect needs owner interaction. Prepare a fresh
public bootstrap, disconnect only the PPC USB serial adapter, verify a bounded
target failure over Ethernet, then reconnect and recover using an entirely new
provider/session. A successful test will not by itself prove every possible
mid-frame interruption; the emulator matrix separately covers all truncations.

Host suspend, target reboot, power-loss/snapshot behavior and full SSH reseeding
remain open. Deadlines currently use guest wall-clock time and were tested with
a stable clock. Administrative exclusivity remains necessary because another
root program can open a device nonexclusively. Every provider/consumer restart
requires fresh bootstrap files; there is no automatic-startup support.

After lifecycle qualification, provision keys through a trusted mechanism and
measure an authenticated PPC session before attempting the requested Mac and
Windows screenshots. The normal daemon's crypto performance, session memory
and timing-security concerns remain separate release gates.
