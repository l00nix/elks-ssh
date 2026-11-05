# Serial laboratory follow-up — 2026-11-05

**The finished product must work without serial.** The owner clarified the
[Ethernet-only deployment requirement](RNG-DEPLOYMENT.md) during this work.
The serial fixture is stopped and is no longer the critical development path.
This page preserves its useful results and unresolved failures; it does not
claim a viable deployment or hardware SSH login.

## Disconnect, recovery and transport limits

The owner physically unplugged the PPC USB serial adapter from the Mac. The
provider exited with no requests served. Over Ethernet, the daemon refused
entropy and exited 1; a second launch also refused, with no remaining SSH
listener. The measured 18.946 seconds includes Telnet login/control overhead.
This was a disconnect before a request, not a physical mid-frame interruption.

After reconnection, a fresh provider/bootstrap let the PPC probe obtain four
seeds across parent and child. Reusing its consumed bootstrap was refused.
The daemon's first recovery attempt failed; a fresh-session retry reached the
deliberately absent host key. Further diagnostic runs at 9600 baud showed:

- 7 of 10 startups reached host-key loading in the first series.
- 2 of 5 in the second series; failed reads received 57, 58 and 58 of 60 bytes.
- Every incomplete response was refused. No bytes or seed fingerprints were
  logged, and no checks were relaxed to make a test pass.

A separate 1200-baud diagnostic build then passed all ten fresh-provider
restarts. That establishes a useful observed mitigation, not proof of the
physical cause or exhaustive reliability. The fixture now defaults to 1200
baud at both ends. ELKS drivers, kernel and firmware were unchanged.

The rebuilt 1200-baud probe passed all 70 QEMU cases and all ten PPC fault
cases; its daemon passed all 12 QEMU startup cases. Hardware healthy probe time
was 5.063 seconds for four seeds. Each linked binary passed the static original
8086/no-FPU audit.

## SSH and key utility evidence

The framed adapter passed the full QEMU SSH suite on the earlier 9600-setting
emulator binary: authentication, command output, key and permission rejection,
repeated login, stdin/EOF, automated PTY input, forced rekey and malformed KEX.
The host served 23 framed responses without a provider error. The final
1200-setting emulator binary separately passed authenticated command execution.
QEMU uses private Unix sockets; these are not physical baud-rate measurements.
See the per-binary hashes in the evidence rather than combining their coverage.

The existing Dropbear key generator now has an isolated ELKS build. Application
adaptations use `uname` for the public key comment and `sync` where `fsync` is
unavailable. No new key-generation algorithm was introduced. On QEMU, the
1200-setting key utility generated an Ed25519 key whose public component matched
an independent host calculation, created a mode-600 private file, and refused
relaunch without fresh bootstrap. Eleven negative cases created no key. Test
images and private material were discarded; evidence retains no private keys.

**The physical key-generation attempt failed at entropy initialization.** The
host received no complete request; no host key was created. This is unresolved
and prevents treating the utility as hardware-qualified. Serial work stopped
after the deployment clarification. No hardware SSH authentication or requested
Mac/Windows SSH screenshot has been completed.

## Evidence and state left behind

[Summary](evidence/20261105-serial-recovery/summary.json),
[9600-byte-count diagnostics](evidence/20261105-serial-recovery/restart-9600-counts.txt),
[1200 restart series](evidence/20261105-serial-recovery/restart-1200.json),
[QEMU full SSH suite](evidence/20261105-serial-recovery/qemu-ssh-suite-9600-build.json),
[final-binary SSH login](evidence/20261105-serial-recovery/qemu-ssh-1200-build.json),
[key generation](evidence/20261105-serial-recovery/qemu-keygen.json),
[hardware key refusal](evidence/20261105-serial-recovery/ppc-keygen-refusal.json).
The evidence directory also contains fault matrices, linked audits and source
hashes. Guest dates are unset; the date above is the host test date.

Experimental binaries remain under `/root/ssh1105` for controlled testing.
No daemon/provider is running; public bootstrap files were removed and the
PPC serial device restored to mode 0644. Ethernet networking and Telnet remain
available. The HP was not changed. Production entropy, power-loss/rollback
behavior, timing security and hardware session memory remain unresolved.
