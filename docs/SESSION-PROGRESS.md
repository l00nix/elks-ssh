# Session validation checkpoint — 2026-11-04

Later on this date: [HP 200LX hardware and linked-daemon audit](HP200LX-PROGRESS.md),
then the [signal-layout fix and repeated 11-case QEMU suite](SIGNAL-LAYOUT.md),
and the [isolated X25519 performance comparison](X25519-COMPARISON.md).
The results below describe the earlier QEMU checkpoint.

Modern macOS OpenSSH 10.3p1 completes stdin/EOF, automated PTY commands and
forced rekeying against the ELKS server in disposable QEMU. The normal server
still refuses startup without secure randomness. This is emulator evidence
with test-only entropy, not a hardware release candidate.

## PTY fixes

The first live-terminal test authenticated and returned `ps` and `/etc/issue`,
but lost its final `PTY_DONE` marker while still returning exit status zero.
The [before-fix result](evidence/20261104-sessions/before-fix-486/result.json)
records that failure. An earlier immediate-input-EOF diagnostic stalled during
PTY commands and was manually interrupted; it is not counted as a completed
regression test.

ELKS releases a PTY's queues when the final slave handle closes. The daemon now
retains its slave handle until channel cleanup, allowing remaining output to
drain after the command exits. Separately, SSH input EOF marks the shared PTY
master's input side closed without prematurely closing the output descriptor.
Both adaptations are confined to `__ia16__` code. No kernel, libc or architecture
changes were made.

## Completed checks

| Fixture | Result |
| --- | --- |
| QEMU 486, MINIX, `--session-suite` | All five cases passed: login, stdin/EOF, live PTY commands, PTY commands with immediate input EOF, rekey output |
| QEMU Pentium, MINIX, `--suite` | All seven prior positive/negative login and output cases passed; pre-authentication limit and child cleanup passed |
| QEMU 486, normal builds, FAT probe fixture | 15 wire, 4 independent cipher, 2 I/O, 1 peer-port, 10 crypto checks and OS probes passed; normal client/server failed closed without RNG |
| Surface native Windows client | Version and algorithm support collected; no ELKS connection result yet |

The PTY command is `echo PTY_BEGIN; tty; ps; cat /etc/issue; echo PTY_DONE`.
Both variants require PTY acceptance, `/dev/ttyp0`, process output, `ELKS 0.9.2`,
the final marker, exit zero and connection-child cleanup. The live variant
uses an open host terminal at 80x24; the EOF variant sends immediate SSH input
EOF. These do not validate interactive shell input, Ctrl-C, Backspace, resize,
canonical/raw terminal EOF semantics or commands waiting for terminal input.

The stdin case compares two lines and the post-EOF marker exactly. The rekey
case uses `RekeyLimit=4K` and verifies all 16,144 payload bytes plus the final
marker, exit zero and child cleanup. Its log contains five received NEWKEYS
messages: the initial exchange and four rekeys. Strict pre-pinned host checking
remained enabled, with Curve25519, Ed25519 and ChaCha20-Poly1305 and no legacy
algorithm overrides.

All original fixture image hashes remained unchanged. Keys and copied guest
images were disposable. The test-only entropy adapter uses the private QEMU
Unix socket described in [ENTROPY](ENTROPY.md); it must not be deployed on PPC.

## Provenance and evidence

The unchanged ELKS baseline is `e1469b64c5809c44d5c822eaeebd0e97d5996289`;
IA16 GCC 6.3.0 builds with `-march=i8086 -mtune=i8086`. Incremental remote build
logs are retained alongside the prior full-build checkpoint. Binary SHA-256:

| Binary | SHA-256 |
| --- | --- |
| QEMU test server | `d827eead4a1e601942a6841dc7244c7743b0d27642faa22488af4b0db13ed8b1` |
| Normal server | `7c6d98b80aeb2495bcc4ba18ac92267f2c460d5dd6d09483a802cfc8610293d7` |
| Normal client | `b87a2f081b5cf9f229408c47d1433480a8db3161cd3e5092134b56d31e2dd41c` |

- [486 session results](evidence/20261104-sessions/sessions-486/result.json),
  [PTY output](evidence/20261104-sessions/sessions-486/command-pty-commands.txt),
  [PTY EOF output](evidence/20261104-sessions/sessions-486/command-pty-input-eof.txt),
  [rekey diagnostics](evidence/20261104-sessions/sessions-486/ssh-rekey-output.txt).
- [Pentium regression results](evidence/20261104-sessions/regression-pentium/result.json)
  and [normal-build probe results](evidence/20261104-sessions/normal-486/result.json).
- [Windows preflight transcript](evidence/20261104-sessions/windows-preflight.txt)
  and [actual screenshot and details](WINDOWS-TESTING.md).
- [Reproduction instructions](BUILDING.md). Private host paths in public logs
  are replaced by generic placeholders; private keys and entropy are excluded.

The 486 session run collected 122 memory samples, with maximum observed heap
break 13,154 bytes, minimum observed SP-minus-break gap 6,790 bytes and process
size 122,704 bytes. The server reserves 16 KiB heap and 8 KiB stack. These samples
are not whole-session peak or worst-case stack bounds. The forced-rekey command
took about 182 host seconds; that is not an 8086 performance estimate.

## Later physical checkpoint — 2026-11-05

The [isolated Ed25519 comparison](ED25519-COMPARISON.md) now includes one
successful Mac-to-PPC SSH command session using independent persistent state,
strict host verification and public-key authentication. It took 27m34s and is
not practical service performance. Native Mac/Windows captures remain pending;
the Surface reconnect is waiting for the owner's certificate review. This
supersedes the earlier hardware-readiness assessment below.

## Remaining work at the earlier session checkpoint

Interactive controls, abrupt disconnects, resource pressure, long sessions,
Windows negotiation/login, the linked daemon's 8086 audit and actual original
8086/8088 execution remain unvalidated. SFTP is not implemented. Hardware-ready
entropy remains a prerequisite for installing the server on the PPC.

The Surface RDP session is responsive after the owner's clipboard-redirection
change. Its native client supports the required algorithms, but support listings
are not an interoperability pass. The [requested PPC screenshots](PPC-CAPTURE.md)
remain pending: the physical PPC currently has neither an SSH listener nor a
random device. Its existing kernel, firmware and other testing were preserved.
