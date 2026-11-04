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
- Do not access PPC or HP 200LX hardware until the user schedules it for this
  project; other testing is in progress. Use disposable emulator images.
- Preserve known-answer tests and run meaningful failure/regression tests.
- Never present a probe or partial handshake as a usable SSH service.
- No weak fallback RNG, embedded secret keys, or authentication bypass.
- Do not spawn subagents without explicit user authorization.
