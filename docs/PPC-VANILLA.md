# PPC vanilla ELKS smoke test — 2026-11-05

Networking autostart is configured, and four X25519 RFC vectors pass on the
physical PPC. Both normal and experimental m15 daemons load when tested
without the crypto probe, then correctly refuse startup because `/dev/urandom`
is absent. **No SSH handshake, authentication or command session was tested.**
All access and output in this checkpoint are through Telnet/FTP, not SSH.

## Target and configuration

The owner made the PPC available at `10.0.0.66` with vanilla ELKS:

```text
ELKS elks 0.9.2 commit e7a56a43 05 Sep 2026 21:21:43 -0600 ibmpc i8086
```

The root is MINIX. The owner had already restored the working PicoMEM network
configuration, `ne0=5,0x300,,0x92`, after the vanilla IRQ12 default failed.
Only `#net=ne0` was changed to `net=ne0` in `/bootopts`. The original was saved
and read back at `/root/ssh1105/bootopts.bak`; the installed file was read back
and synced. `/etc/rc.sys` uses this variable to run `net start $net`.
The existing `/etc/net.cfg` enables DHCP and starts Telnet and FTP.
Those files were inspected but not changed.

No reboot was performed, so autostart is configured, **not yet boot-verified**.
The kernel, firmware, accounts, serial configuration and other PicoMEM work
were left unchanged. Test files are isolated under `/root/ssh1105`; no SSH
service was added to boot configuration. Rollback of this one setting is:

```sh
cp /root/ssh1105/bootopts.bak /bootopts
sync
```

## Hardware checks

| Check | Result |
| --- | --- |
| Normal daemon startup | Loads, passes signal setup, refuses missing `/dev/urandom`, exit 1 |
| Experimental m15 startup under concurrent load | Shell reports insufficient memory, exit 2 |
| Experimental m15 after probe exits | Loads, refuses missing `/dev/urandom`, exit 1 |
| X25519 Alice public key | PASS, 110 target seconds |
| X25519 Bob public key | PASS, 97 target seconds |
| X25519 Alice shared secret | PASS, 89 target seconds |
| X25519 Bob shared secret | PASS, 92 target seconds |
| Networking after tests | Telnet and FTP accessible; no SSH listener |

The X25519 executable is the audited `m15bench` linked with the same m15
objects as the experimental daemon. Its hash is
`2a0078297993fb9160aea555c6a154df9f97665b8f1eddf2f55982064c23340a`.
Both server hashes and transfer/readback verification are in the evidence.
The QEMU entropy binary was **not** installed.

The 12-vector batch was deliberately stopped after the four RFC vectors to
bound this smoke test and release its memory for the isolated startup check.
Only the verified probe PID was terminated. Its shell exit status is 143 and
the raw harness reports `passed: false` because a full-suite completion marker
was not produced. That is not a vector mismatch; it is also not a 12-vector
pass. Remaining edge cases and Ed25519 execution are untested on this install.
The Ed25519 probe was staged but not run.

The first memory snapshot included the probe and two Telnet sessions: about
205 KiB of main memory was free, with a largest displayed free block of
182,352 bytes. After the probe and extra session exited, about 286 KiB was free,
with a 246,352-byte block. The experimental daemon then loaded. These are
snapshots, not peak bounds or proof that a complete SSH session fits.
`meminfo` displayed negative XMS totals; those values are not treated as usable
memory measurements.

The clock was unset (Jan 01 in daemon logs). Dates here come from the host;
probe durations use target elapsed seconds. Networking and inspection commands
were active during part of the run. The HP comparison used a different probe
layout and serial access, so these timings are not a controlled CPU speed ratio.

## Remaining gates

A hardware-appropriate fresh entropy provider is needed before an actual
client connection. The [entropy contract](ENTROPY.md) is not yet implemented
for hardware; no static seed, weak fallback or unauthenticated network source
was substituted. The [m15 runtime and timing-security blockers](M15-DAEMON.md)
also remain unresolved. No hardware SSH release candidate is established.

Mac/Windows SSH screenshots remain pending a real verified login. This
checkpoint produces hardware test transcripts, not screenshots of SSH sessions.
Evidence: [20261105-ppc-vanilla](evidence/20261105-ppc-vanilla/).
