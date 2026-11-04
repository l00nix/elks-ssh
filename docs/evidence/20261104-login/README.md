# Login checkpoint evidence

See [the report](../../LOGIN-PROGRESS.md) for interpretation and limitations.
`binaries.json` identifies the final binaries tested; these are development
artifacts, not released executables.

- `qemu-486`: basic login and delayed-output test, including serial transcript
  underlying the published guest screenshot.
- `qemu-pentium`: full seven-case suite and preauthentication connection limit.
- `regressions`: normal server/client refusal without entropy, wire/cipher/I/O
  checks and standalone crypto/OS probes.
- `entropy-short`, `entropy-silent`: final test server refuses partial/missing
  entropy responses.
- `fixture.json`: provenance of the unchanged source image and the tested MINIX
  fixture. `login-fixture-build.log` is a separate reproduction check using an
  output path containing spaces; filesystem timestamps make its hash different.
- `login-*.log`: remote compiler output. Builds proceeded through the initial
  QEMU port, pipe/session changes and connection-limit changes, then the final
  help-text correction (`login-help-test.log`). The normal server was linked
  with the new heap default (`login-normal-server-final.log`) and rebuilt after
  the help correction (`login-help-normal.log`). The client and regression tools
  have their own logs. Private host paths are replaced with `$ELKS`, `$BUILD`
  or `$SOURCE`; compiler diagnostics are otherwise retained.

`memory.json` records sampled guest `ps` output, not a peak-memory bound. Client
diagnostics replace ephemeral local paths with `$TEST`; public fingerprints
are from disposable keys. No private keys, entropy bytes, images or credentials
are included. Tests used QEMU only and left the input images unchanged.
