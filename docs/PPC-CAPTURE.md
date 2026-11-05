# Requested Mac and Windows SSH captures

The owner requested screenshots from macOS and the Surface Laptop connecting
to the physical PPC over SSH and executing `ps` and `cat /etc/issue`.
These captures are pending; QEMU or Telnet output must not be presented as
physical PPC SSH evidence.

## Readiness check — 2026-11-04

The physical PPC answered through its existing Telnet service. Read-only checks
showed ELKS 0.9.2, a MINIX root filesystem, and no listening SSH service on port
22 (connection refused). Neither `/dev/urandom` nor `/dev/random` exists.
The usual `/bin/dropbear`, `/bin/sshd`, `/usr/sbin/sshd` and `/root/authkeys`
paths are absent. `ps` and `cat /etc/issue` were collected locally through
Telnet solely for readiness assessment; `/etc/issue` reports `ELKS 0.9.2`.

No kernel, firmware, boot settings, accounts or services were changed. The
other PicoMEM development work and attached storage were left intact.

Windows App initially stalled at “Configuring remote PC…”. The owner reported
disabling clipboard redirection and unlocking the Surface; the retained session
then became responsive. Native Windows preflight confirmed OpenSSH 9.5p2 and
support for the three algorithms currently used in QEMU. See
[Windows observations and the actual preflight screenshot](WINDOWS-TESTING.md).
This is not a Windows-to-ELKS connection result.

## Required before capture

1. Complete a hardware-appropriate strong entropy path and qualify its failure
   behavior. The private Unix-socket QEMU adapter is not a physical deployment
   option; do not install it on the PPC or substitute a static seed file.
2. Audit the linked server's 8086 compatibility and establish sufficient session
   memory. Reproduce the required commands and PTY behavior in the emulator.
3. Stage a temporary PPC candidate without replacing its current kernel or
   firmware. Provision fresh test credentials through a trusted path, pin the
   host key and preserve an independent recovery connection.
4. Validate the native Windows client separately, as described in
   [WINDOWS-TESTING](WINDOWS-TESTING.md).

## Capture contents and provenance

For each client, use a clean terminal showing the actual SSH command and its
successful remote session, followed by `ps` and `cat /etc/issue`. Record the
client OS/version, exact SSH executable/version, PPC build, server binary hash,
host-key fingerprint and entropy method. Strict host checking must remain on.
Capture actual application pixels and retain the matching command transcript.
Keep passwords, private keys and unrelated desktop contents out of published
images. Do not use a rendered transcript or generated image as a screenshot.

Keep the Mac and native Windows results separate. Windows Terminal behavior,
including input, line endings and PTYs, is distinct from protocol negotiation.
A successful connection to an emulator is useful development evidence but does
not satisfy these requested PPC screenshots.

## Vanilla PPC check — 2026-11-05

The owner made the PPC available again. [Hardware smoke tests](PPC-VANILLA.md)
confirm four X25519 vectors and fail-closed daemon startup on vanilla ELKS.
Networking autostart was configured. No SSH login occurred; the requested
Mac/Windows SSH captures still require a hardware entropy provider.
