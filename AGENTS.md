# Project constraints

- User-space only. Do not change ELKS kernel, libc or architecture to make a
  port work. Report missing capabilities and alternatives instead.
- Minimum ISA: original 8086/8088, no FPU. Audit linked code, not just source.
- Do not claim all ELKS CPU/platform/version combinations pass without evidence.
- Use existing SSH/crypto implementations with pinned provenance and licenses.
- Compare designs and their effects on the whole system before implementing.
- Keep new adaptation code isolated and common code changes minimal.
- The user explicitly authorized a public fork of the existing public project.
  Preserve upstream history and attribution. Do not invite ghaerr before a first
  viable release candidate. At that milestone, prepare the test package and
  revisit the invitation with the user; none is authorized for this prototype.
- The user authorized PPC SSH testing and Mac/Windows client screenshots on
  2026-11-04. Preserve other projects' kernel/firmware and running tests; this
  authorization does not make the QEMU-only entropy adapter hardware-ready.
  The user made the HP 200LX available on BH00K9NP serial on 2026-11-04;
  hardware capability/crypto testing is authorized. The owner made the PPC
  available again on 2026-11-05 at 10.0.0.66
  for networking autostart and SSH testing on vanilla ELKS. Preserve their
  PicoMEM firmware and other work. Use disposable emulator images for
  development and failure testing.
- Preserve known-answer tests and run meaningful failure/regression tests.
- Never present a probe or partial handshake as a usable SSH service.
- No weak fallback RNG, embedded secret keys, or authentication bypass.
- The owner clarified on 2026-11-05 that the finished SSH service must work
  on Ethernet-only computers without a serial connection. Serial entropy is
  a laboratory fixture, never a required deployment interface. Do not make
  companion hosts, LAN helpers and extra RNG hardware runtime requirements.
  The owner explicitly requires independent operation after one-time secure
  provisioning. Qualify persistent generator state and recovery before deployment.
- The PPC uses a PicoMEM-backed HDD image, not a CF card. The owner can create
  a separate disposable HDD image for power-loss testing. Preserve the working
  image and PicoMEM firmware; coordinate physical power interruption with them.
- Do not spawn subagents without explicit user authorization.
- A fresh private PPC image was prepared under
  `~/.local/share/elks-ssh/ppc-trial-20261105/sshtrial.img`; the owner reports
  it booted. The first TCP/SSH attempt was stopped after 7m24s without command
  output; login and host verification completion are not established. The
  owner's console photo shows PID 9 sleeping and child PID 11 runnable at 93%
  CPU, with no auth success/error logged at that initial checkpoint.
  Temporary serial login is now active on BG02T8E2 at 9600 baud. Root shell
  is at /root/sshtrial; commands must be short/paced to avoid input loss from
  line-editor redraw. Local control helper is under the ignored
  feasibility/test-output/ppc-independent-20261105/serial_control.py.
  Abandoned child 11 was force-stopped after SIGTERM did not stop it. A separate
  audited/QEMU-tested baseline diagnostic binary /root/sshtrace identified the
  first X25519 calculation as unfinished at its 180-second test limit. Test
  child 40 and diagnostic listener 36 were stopped; original /bin/sshtrial was
  restored afterward, state lock absent. Inspect fresh PIDs before
  further actions. Serial is control only, never entropy or private-key/state
  transfer. The ordinary forked persistent m15 variant fails shell fork with
  ENOMEM in QEMU. The same worker (SHA 67e67ec54461a9aca467eedbd5503eebcd8a872ee3eb3aa568102db68bf77752)
  with the small single-worker launcher passes eleven QEMU session cases,
  malformed KEX rejection, persistent-state checks and stop/reap testing. A
  temporary hardware comparison of that exact pair completed: both X25519
  operations took 93 seconds; Ed25519 signing remained unfinished at the
  305-second observation. Client was operator-stopped at 308.8 seconds, not a
  demonstrated server timeout. Listener 79 and worker 82 were removed; original
  /bin/sshtrial restored as PID 99, lock absent. Inspect fresh PIDs before acting.
  The comparison binaries remain staged under /root but are not running. No
  hardware SSH login has succeeded. Preserve original startup. An independent
  c25519 Ed25519 public-vector probe passes host/QEMU tests but is not an SSH
  backend and has unreviewed strict-input and timing requirements.
  It starts experimental SSH on TCP 2222 and disables Telnet/FTP.
  Use that directory's `connect.sh` and pinned host key for this trial. Never
  print/fetch secret state or keys through plaintext control, publish the image,
  run the public byte-printing probe against it, or clone/restore it.
  The Mac's initial image copy has been deleted after the owner's boot
  confirmation; this is not secure erasure. Client access files are retained.
  The existing public PPC fixture is at recovery generation three after
  the non-disclosing checker test. Do not confuse public and private states.
