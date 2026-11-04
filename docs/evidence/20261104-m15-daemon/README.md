# m15 daemon evidence

These are failed integration and successful component checks, not release evidence.
See [the checkpoint report](../../M15-DAEMON.md).

- Root audits describe the first corrected far-section build.
- `qemu-ssh` records three malformed-KEX rejections followed by authenticated
  command failure. Later session checks were skipped.
- `exec-diagnostic` contains final daemon audits and a repeat identifying
  `execv` errno 12, plus successful normal-build RNG refusal.
- `qemu-ed-diagnostic` records the isolated four-check Ed25519 pass.
- `qemu-primitives` was interrupted during Ed25519 after 12 X25519 passes.
- `qemu-primitives-repeat` reproduces the 300-second Ed25519 timeout after m15.
- `ed25519-muldi3.txt` shows the operand-dependent carry branches in linked code.
- `provenance.json` identifies source base, toolchain and preserved normal binaries.

Paths are replaced by `$BUILD`, `$ELKS`, `$REPO` or `$TMP`. No private test keys
are retained. QEMU register dumps belong only to public-vector probes. Earlier
failed placement binaries and full ELF/maps remain in ignored local test output.
