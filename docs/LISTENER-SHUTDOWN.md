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
