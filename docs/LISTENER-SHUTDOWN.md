# Experimental listener shutdown

The successful physical PPC SSH test ended with `sshlisten accept: Error 512`
when the listener was deliberately stopped. ELKS defines 512 as `ERESTARTSYS`.
The listener already received its stop signal and cleaned up, but its error
handling only recognized `EINTR`, causing misleading output.

The isolated listener now checks its stop flag before reporting an interrupted
`select` or `accept` as an error. If a socket is accepted during shutdown, it is
closed without launching another worker. Ordinary socket errors retain their
diagnostics. This changes no SSH, authentication, random-state or kernel code.

The regression test first logs in, opens an unauthenticated worker, stops the
listener and checks that the worker disappears and the connection closes. It
then starts and stops an idle listener on a separate guest-only port. Both
shutdown logs must be free of socket-error messages. The separate port avoids
making the idle-stop test depend on immediate reuse of the first port.

| Check | Original launcher | Fixed launcher |
| --- | --- | --- |
| SSH command login | Pass | Pass |
| Stop removes connected worker and closes socket | Pass | Pass |
| Intentional stop produces no socket-error log | Fail | Pass |
| Idle listener stops cleanly | Not reached | Pass |
| Persistent state matches reference; base image unchanged | Pass | Pass |

The fixed launcher SHA-256 is
`1170dcf7d5b4b004a2bc9991cc85eaaf04a7fa352daa5f8ac3eb75375d0b8bf9`.
Its linked-code original-8086/no-x87 audit passes. These are QEMU results;
the ongoing physical Windows compatibility trial uses the previously qualified
launcher, so its results must not be attributed to this fix.

Evidence: [before](evidence/20261105-listener-stop/before/result.json),
[before serial](evidence/20261105-listener-stop/before/serial.txt),
[after](evidence/20261105-listener-stop/after/result.json),
[after serial](evidence/20261105-listener-stop/after/serial.txt), and
[ISA audit](evidence/20261105-listener-stop/after/sshlisten-audit.json).

During test development, an added `wait PID` check failed because the ELKS shell
had already reaped and reported the job; the final test checks process and socket
state directly. A first idle restart on the original port did not stay running;
the final test uses a separate port and does not claim to qualify port reuse.

## Idle child cleanup — 2026-11-06

The completed native Windows session left worker 233 as a zombie while the
physical listener waited for the next connection. Serial maintenance recovered
after the owner restarted getty; stopping the listener removed both process
entries. The authenticated command result and client exit zero still stand,
but the old idle-cleanup claim was incorrect.

The regression previously counted only rows containing the server command.
ELKS omits a zombie's command name, so the test could report success while an
exited worker remained. The check now also rejects `Z` process entries in the
isolated guest. It reproduces the problem with the prior launcher: login exits
zero but worker 15 remains unreaped.

The candidate waits in its existing child-reaping loop while a worker is
active, rather than entering another blocking `accept()`. ELKS's listening
socket readiness can otherwise send it into `accept()` before a connection
arrives. It polls `waitpid(..., WNOHANG)` with a 100 ms sleep and accepts the
next connection only after reaping the previous worker. No kernel or libc
changes are needed.

This changes admission behavior: an additional connection can wait in the
existing TCP listen queue without an SSH banner; it no longer necessarily
closes immediately. Only one SSH worker runs at a time. The test checks that
an additional client receives no banner and does not allocate another worker,
then verifies cleanup and subsequent authenticated sessions. The backlog is
not a second authenticated session or a promise of immediate rejection.
`listen(..., 1)` is retained, but this test does not establish a network-memory
bound under connection floods; it establishes the one-worker process limit.

An earlier signal-handler candidate was rejected in QEMU: it reaped the first
worker, but the next connection timed out. It was never installed on the PPC.
The wait-loop candidate passes the expanded QEMU regression: seven command/
authentication cases, three malformed X25519 inputs, one-worker admission,
connected and idle shutdown, and persistent-state consistency. The optimized
field-arithmetic server also passes five login/signature cases with this same
launcher. Five additional stdin/PTY/rekey cases also pass with this pair;
[terminal-control warnings remain open](SESSION-PROGRESS.md). Every completed
case leaves no zombie process entry.

The new launcher SHA-256 is
`8d700dfead1997f95cac25f48c3e3421cd037efbeb21115f040247e2b4ef8ebd`.
Its linked-code original-8086/no-x87 audit passes. On the physical PPC, three
banner/disconnect attempts subsequently passed with no remaining workers or
zombies. One additional connection waited without receiving a banner or
allocating a second worker. This is admission/cleanup evidence, not an
authenticated hardware session for the new binary pair.

The first hardware attempt used a 15-second banner deadline and expired before
a banner arrived. The server later logged a socket-address failure after that
client closed, and the worker was reaped. A retry allowed 90 seconds; all three
banner checks completed. The queued client that closed before acceptance also
produced a socket-address error and was cleaned up. No listener accept/select
error was reported. See [physical results](evidence/20261106-ppc-field-o2/listener-result.json).

The PPC now runs the optimized worker with this launcher temporarily on port
2222. Startup files and private keys/state were not replaced or rolled back.
The native Mac full-login test is prepared and awaits user launch because
Computer Use explicitly blocks access to macOS Terminal.

Evidence: [reproduction with prior launcher](evidence/20261106-listener-reap/before/result.json),
[expanded regression](evidence/20261106-listener-reap/queue-after/result.json),
[optimized server pairing](evidence/20261106-listener-reap/field-queue/result.json),
and [ISA audit](evidence/20261106-listener-reap/listener-audit.json).
