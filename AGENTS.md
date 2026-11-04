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
  hardware capability/crypto testing is authorized. Leave PPC testing to the
  owner while they finish PicoMEM work. Use disposable emulator images for
  development and failure testing.
- Preserve known-answer tests and run meaningful failure/regression tests.
- Never present a probe or partial handshake as a usable SSH service.
- No weak fallback RNG, embedded secret keys, or authentication bypass.
- Do not spawn subagents without explicit user authorization.
