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

1. Compare established implementations suited to 16-bit arithmetic to improve
   the slow Curve25519 baseline. The HP signal-callback rejection is resolved
   for the measured build by [linking the unchanged libc callback first](SIGNAL-LAYOUT.md).
2. Extend disposable QEMU tests for interactive shell input, terminal
   resize/control keys and abrupt disconnects; retain stdin/EOF and rekey checks.
3. Run the [Windows 11 client matrix](WINDOWS-TESTING.md) against that fixture.
   Audit each changed linked candidate and measure memory under long sessions,
   rekeying and resource pressure; samples are not peak bounds.
4. Qualify the production entropy source through an existing ELKS interface,
   including missing/short input, disconnect and recovery behavior.
5. Continue the authorized HP 200LX tests; arrange PPC use again with the owner
   after their PicoMEM work and when a hardware SSH candidate is ready. File
   transfer and key-generation utilities follow the core service.

PPC testing is now authorized, including [Mac and Windows SSH captures](PPC-CAPTURE.md)
of `ps` and `cat /etc/issue`. Readiness checks found no installed SSH service or
random device; those screenshots remain pending a hardware-appropriate entropy
path and candidate. The owner has since made the HP 200LX available on serial;
see [hardware progress](HP200LX-PROGRESS.md). The PPC is currently left to the
owner's PicoMEM work.
