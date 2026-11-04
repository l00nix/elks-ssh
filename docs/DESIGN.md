# Design decision: continue the existing ELKS Dropbear port

Status: initial development, 2026-11-04. No kernel, libc or architecture changes.

## Existing work

[ghaerr/ssh-daemon-elks](https://github.com/ghaerr/ssh-daemon-elks) is already a
fork of [parabyte/ssh-daemon-project](https://github.com/parabyte/ssh-daemon-project).
Its README's request for an ELKS maintainer to take over predates this project;
it should not be attributed to ghaerr as a new instruction to us.

We retain its history starting at commit
`2bee5b852fa3789a8f5539a20291020d53eea427` (2026-04-19). The source identifies
Dropbear 2025.89. Its ELKS Makefile builds **dbclient**, with medium-model code,
native socket adaptations, and selected Curve25519/Ed25519/ChaChaPoly algorithms.
The presence of generic server sources is not evidence of a working ELKS server.

## Alternatives considered

| Foundation | Benefit | Cost or unresolved issue |
| --- | --- | --- |
| Existing ELKS Dropbear port | Reuses IA16 build and socket adaptations; same protocol source can serve client/server | Client-focused; server integration and resource/security review still needed |
| Current upstream Dropbear | Maintained protocol and algorithm implementation, build-time feature selection | Must redo ELKS adaptations or forward-port the existing ones |
| TinySSH | Small server-focused code with modern crypto and subsystem support | No ELKS port found; current channel buffer is 131072 bytes, above a near-data segment |
| SSH-1-era source | Historically smaller code | Cannot satisfy the modern SSH-2 client requirement |

Decision: use the existing ELKS Dropbear port as the foundation, compare its
changes with current Dropbear, and carry forward only reviewed adaptations.
The independent crypto probes were written before locating this port and are
retained as measurements/tests, not as a new mixed-implementation SSH stack.

## First corrections and remaining gates

The inherited Makefile enabled `DROPBEAR_ELKS_WEAK_RANDOM=1`. In `src/dbrandom.c`
that permits operation after failure to read the random device, while mixing in
configuration-file material. That is unsuitable as a security baseline. Our
default ELKS build explicitly disables it, so missing randomness is fatal.
This change does not provide a new entropy source.

The ELKS build also now explicitly selects `-march=i8086` at compilation and
linking, in addition to `-mtune=i8086`. The client still requires its own complete
linked-code and runtime audit; passing the standalone probes does not certify it.
The reproduced build reports integer-truncation and incompatible-pointer
warnings. These are recorded for investigation, not dismissed as harmless.

Before enabling an ELKS daemon:

1. Compare this fork against current upstream security fixes and 16-bit integer,
   allocation, packet-length and timeout assumptions.
2. Establish a sound user-space entropy strategy using existing ELKS interfaces.
   Predictable clocks/configuration, repeated fixed seeds, and key material
   copied into emulator snapshots are not production entropy solutions.
3. Measure total memory, call-chain stack depth and Ed25519/X25519 runtime.
   The inherited client stack reservation is 2048 bytes; it is not yet validated.
4. Port server PTY/session handling and account checks using existing APIs.
   The inherited configuration disables server multiuser/privilege dropping;
   simply enabling server compilation would not establish correct isolation.
5. Test genuine modern OpenSSH sessions, rekeying, authentication rejection and
   connection cleanup before extending the service to SFTP.

SFTP must use normal ELKS file operations and report underlying filesystem
limits accurately. Separate optional executables and shared-library code should
be compared by measured memory/disk costs. No PicoMEM-specific service is needed.

## CPU and platform scope

Original 8086/8088 instructions are the baseline for all shipped ELKS binaries.
That baseline is intended to run on later compatible x86 CPUs, but ABI, kernel
configuration and machine differences remain independent compatibility axes.
QEMU PC tests with 486/Pentium CPU models exercise later CPUs only. They neither
emulate 8086 bus/timing behavior nor prove NEC, PC-98, embedded 8018x or other
machine support. Record each verified combination; do not equate a CPU flag
with universal backward/forward compatibility or support for future ELKS APIs.

Hardware tests will be scheduled with the owner after an emulator-tested
candidate exists. No PPC or HP 200LX connection is authorized at this stage.
