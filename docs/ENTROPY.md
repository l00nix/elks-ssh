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
It would not establish standalone hardware security. No provider is implemented
or selected for release yet.

Host keys establish identity; they do not replace session entropy. Never use a
host key, clock, configuration file, fixed seed or copied image as the sole
random source. The public fixed keys in the regression vectors are confined to
test executables; they are not usable service keys.
