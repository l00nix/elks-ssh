# Development milestones

1. **Feasibility baseline:** reproduce the existing client build; run isolated
   crypto/OS probes; preserve upstream history; identify security and API gaps.
2. **Server port:** compile the existing Dropbear server against unchanged ELKS,
   using native sockets and PTYs; audit 16-bit assumptions and memory. No public
   listening service until authentication and randomness are sound.
3. **SSH interoperability:** modern OpenSSH key exchange, host verification,
   public-key login, commands, interactive shell, rekeying and cleanup. Add
   negative packet/authentication tests and regression checks for other services.
   Validate Windows 11's native OpenSSH client separately from macOS/Linux;
   record the Windows build, client version and terminal used.
4. **Hardware candidate:** arrange PPC and HP 200LX access with the owner;
   measure runtime, memory, failures and recovery. Retain captured evidence.
5. **Companion tools:** SFTP subsystem and small key utility; native generation
   depends on the validated entropy source. Outbound tools are separately scoped.
6. **First viable release candidate:** reproducible binaries, documented CPU/ELKS
   matrix, installation/rollback instructions and honest limitations. Revisit
   inviting ghaerr only at this milestone. No invitation has been sent.

Current checkpoint: milestones 1 and 2 have probe/build/regression evidence;
milestone 3 now has QEMU public-key login, remote commands, output integrity,
repeated connection cleanup and negative authentication tests. Stdin/EOF,
automated PTY commands and forced rekeying now pass. Full interactive sessions
and broader failure handling remain open. Runtime
memory sampling is preliminary; production entropy and practical hardware
crypto performance remain release gates. The normal daemon now passes the
static 8086 audit for its recorded hash; each changed candidate needs re-audit.
See [session progress](SESSION-PROGRESS.md).

The public fork is authorized. Publication of a secure release still requires
evidence that these criteria are met; the current feasibility milestone is not
a release candidate.

## Next development order

The owner clarified that deployment must work on Ethernet-only systems without
serial. First resolve the [randomness deployment model](RNG-DEPLOYMENT.md);
the serial fixture is stopped and is no longer the critical path. The following
crypto, session and platform work remains relevant.

1. Resolve the [experimental m15 integration](M15-DAEMON.md) failures before
   choosing a production backend: combined-probe Ed25519 failure, shell `ENOMEM`,
   and data-dependent arithmetic timing. The code now fits two segments and
   authenticates in QEMU, but does not run commands. Preserve the existing normal
   daemon and exclude the smaller m15 variant after its vector failures.
   The HP signal-callback fix remains [application-only](SIGNAL-LAYOUT.md).
2. Extend disposable QEMU tests for interactive shell input, terminal
   resize/control keys and abrupt disconnects; retain stdin/EOF and rekey checks.
3. Run the [Windows 11 client matrix](WINDOWS-TESTING.md) against that fixture.
   Audit each changed linked candidate and measure memory under long sessions,
   rekeying and resource pressure; samples are not peak bounds.
4. Qualify the production entropy source through an existing ELKS interface,
   including missing/short input, disconnect and recovery behavior.
5. Resume PPC SSH sessions when the Ethernet-only randomness design permits
   them. Keep the HP on console until separate networking and its memory cost
   are resolved. File transfer follows the core service; an isolated native
   key utility now has QEMU evidence.

PPC testing is now authorized, including [Mac and Windows SSH captures](PPC-CAPTURE.md)
of `ps` and `cat /etc/issue`. Readiness checks found no installed SSH service or
random device; those screenshots remain pending a hardware-appropriate entropy
path and candidate. The owner has since made the HP 200LX available on serial;
see [hardware progress](HP200LX-PROGRESS.md). The PPC was subsequently made available again.

The owner made the PPC available again on 2026-11-05 for the
[vanilla ELKS smoke test](PPC-VANILLA.md). Both daemons load alone and refuse
missing entropy; four X25519 RFC vectors pass. Complete hardware sessions and
the rest of the hardware crypto suite remain unvalidated.

The [serial entropy checkpoint](SERIAL-ENTROPY.md) implements an isolated
controlled-cable provider. Software fault matrices and PPC daemon startup pass.
The [disconnect/recovery follow-up](SERIAL-RECOVERY.md) records physical tests
and remaining failures. Native key generation passes QEMU but refused entropy
on the PPC. Next: an Ethernet-only deployment design and its prerequisites.
No hardware listener or automatic service is installed.
