# Secure randomness: unresolved prerequisite

The prepared ELKS tree at `e1469b64c5809c44d5c822eaeebd0e97d5996289`
has no `getrandom` or `/dev/urandom` implementation found in the inspected
kernel/libc/application C sources and headers. The tested image cannot open
`/dev/urandom`. This finding is specific to that source/image, not every ELKS
fork or future version. No kernel or libc changes were made.

Dropbear currently requires a fresh 32-byte seed from its configured random
source during initialization and reseeding. Missing input is fatal. The ELKS
server now performs that check before loading host keys and opening listening
sockets; per-connection reseeding remains in place.

## Options to evaluate

| Option | Advantage | Work and limitations |
| --- | --- | --- |
| Trusted host or hardware RNG through an existing device interface | Can provide fresh entropy without changing ELKS | Define authenticated/private provisioning, framing, blocking, short-read and disconnect behavior; requires an external source |
| User-space generator with securely provisioned persistent state | Potentially standalone after provisioning | Needs a reviewed generator, safe state replacement before use, fork separation, power-loss handling and recovery. Copied disks and snapshots can repeat state; a static seed file is insufficient |
| Timing/jitter collection | No extra hardware in principle | No validated minimum entropy estimate for original 8086/8088, emulation or these machines; not accepted as a fallback |

Recommended development order: validate a fresh external source in an isolated
QEMU test harness, then separately decide whether the first hardware candidate
requires that source or can support a reviewed standalone state design. An
emulator-fed source would prove interoperability only for that assisted setup.
It would not establish standalone hardware security. A QEMU-only adapter now
exists for development; no provider is selected or implemented for release.

Host keys establish identity; they do not replace session entropy. Never use a
host key, clock, configuration file, fixed seed or copied image as the sole
random source. The public fixed keys in the regression vectors are confined to
test executables; they are not usable service keys.

## Recommended end-state direction

Keep the SSH implementation independent of the entropy transport. Prefer a
validated hardware RNG reachable through an existing ELKS device interface for
operation without a companion computer. A trusted-host source is useful for
interoperability development and could become an explicitly assisted deployment
option. Neither implies new kernel or libc APIs.

A software-only standalone mode is a separate feasibility milestone, not a
fallback. It would require securely provisioned state, a reviewed generator,
state advancement durable before output, process separation and recovery rules.
Power loss, cloned CF cards and restored images must not repeat generator state.
We have not shown that the target filesystems can provide the required durability
and rollback protection. See [RFC 4086](https://www.rfc-editor.org/rfc/rfc4086.html)
for the distinction between a strong generator and unpredictable seed material.

## Development-only QEMU adapter

`make -f Makefile.elks PROGRAM=dropbear TEST_ENTROPY=1` produces a separate
`dropbear-qemu`. It obtains each fresh 32-byte seed from the host OS through
QEMU's second serial port, connected only to a private Unix socket. The normal
`dropbear` and `dbclient` builds retain their existing secure-source requirement.
The adapter must never be installed on physical machines or treated as a
production entropy service.

The harness generates new host/client keys per run, pins the host public key
before connecting and destroys the keys and disposable image afterwards. It
forwards one loopback-only TCP port with restricted guest networking. The second
serial port is entirely emulated; no physical adapter is opened.

The test framing is the EGD blocking-read request `{2,32}` followed by exactly
32 bytes, with a five-second guest-time response deadline. Short and missing
responses are fatal after Dropbear's retry. The adapter uses existing termios,
read/write and select calls. It disables Dropbear's optional seed writeback so
that testing cannot create a regular `/dev/urandom` file.

This private test channel has **no protocol authentication or replay protection**;
it relies on the trusted host and private socket. It is not a release-ready
protocol for serial cables, networks or untrusted entropy devices. Hardware
source qualification, transport protection, disconnect/recovery behavior and
replay resistance remain release gates. No standalone security claim follows
from a passing emulator test.
