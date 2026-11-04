# ELKS SSH

An experimental continuation of [ghaerr/ssh-daemon-elks](https://github.com/ghaerr/ssh-daemon-elks),
itself forked from [parabyte/ssh-daemon-project](https://github.com/parabyte/ssh-daemon-project),
to bring SSH-2 login and secure file transfer to
[ELKS](https://github.com/ghaerr/elks), starting with the original **8086 and
8088** instruction set. The project builds on existing ELKS user-space APIs;
kernel and architecture changes are out of scope.

**Development has started. This is a feasibility prototype, not a working or
secure SSH server.** Both client and server now compile for ELKS. Tests cover
cryptographic code, 16-bit buffer/wire handling and startup refusal without
secure randomness. No network login,
key generation or file-transfer service is installed by these probes.

## Planned suite

| Component | Purpose | Status |
| --- | --- | --- |
| SSH daemon | SSH-2 transport, public-key login, shell and remote commands | Compiles; startup checks only |
| SFTP subsystem | Secure file transfers through native ELKS filesystem APIs | Planned |
| Key utility | Public-key display, fingerprints, eventually key generation | Planned |
| SSH/SFTP clients | Outbound connections from ELKS | Later feasibility work |

The existing **Dropbear ELKS port is our starting point**. Its inherited ELKS
deliverable was `dbclient`; our new server build remains experimental and has
not completed a successful SSH login. The inherited source and Git history are
preserved. TinySSH was considered as an alternative; isolated comparative crypto probes live under
`feasibility/` and do not replace the Dropbear protocol implementation.
See [the architecture comparison](docs/DESIGN.md).

## Compatibility commitment

- Compile with `-march=i8086 -mtune=i8086`, without an x87 requirement.
- Audit the **linked executable**, including runtime/library code, for later
  instructions. Do not infer 8086 support from compiler flags alone.
- Test on QEMU with multiple later x86 CPU models and isolated ELKS images.
- Schedule real 8086/8088-class testing separately. QEMU's PC CPU models do
  **not** prove original 8086/8088 execution or hardware performance.
- Keep CPU compatibility separate from ELKS-version and machine compatibility.
  Older ELKS releases, non-PC platforms, NEC CPUs and future releases need
  explicit validation; universal compatibility is a target, not a current claim.

The PPC and HP 200LX are in use by other tests. **Do not connect to them,
upload files, reboot or reconfigure them until the owner schedules this work.**

## Build and test

See [BUILDING](docs/BUILDING.md) for the prepared ELKS toolchain, remote-build
workflow and disposable QEMU tests. Testing tools are separate from the minimal
external build path. The proposed integration follows ELKS's `buildext.sh` and
`elkscmd/ExtApplications` conventions; probes are not automatically installed
as a login service.

See [VALIDATION](docs/VALIDATION.md) for measured results and limitations, and
[ROADMAP](docs/ROADMAP.md) for the staged development plan.

Initial results: the existing client builds with weak entropy disabled; ten
standalone crypto checks and the OS probes pass in QEMU on 486 and Pentium CPU
models. Both probe executables pass the static 8086 instruction audit. The
daemon and real 8086/8088 execution remain unverified.
The next checkpoint adds a server build, 32-bit SSH sequence/channel handling
and fifteen production-code regression checks with four independent cipher
vectors. See [server progress](docs/SERVER-PROGRESS.md) and the unresolved
[entropy strategy](docs/ENTROPY.md). No successful SSH connection is claimed.

![ELKS wire regressions and server startup refusal in QEMU](docs/screenshots/qemu-server-startup.png)

The server capture shows the expected refusal without secure randomness.
[Current test evidence](docs/SERVER-PROGRESS.md) includes build logs and hashes.

![Crypto feasibility tests running in ELKS under QEMU](docs/screenshots/qemu-crypto.png)

Actual emulator capture, not an SSH login or hardware test. Capture provenance
and the serial transcript are in [VALIDATION](docs/VALIDATION.md).

## Architecture guidance

The design follows the layering, maintainability and regression-testing advice
in [ghaerr's PicoMEM discussion](https://github.com/ghaerr/elks/discussions/2841#discussioncomment-19387609)
and [ELKSWeb external-build guidance](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-19053594).
Those discussions do not constitute endorsement or approval of this SSH project.
The detailed [project constraints](docs/DESIGN-CONSTRAINTS.txt) are retained here.

Reliable session randomness, total memory/stack usage, account isolation,
packet bounds and practical handshake time remain feasibility gates. A missing
OS capability will be documented rather than worked around with a kernel hack.

This repository is a public fork, as authorized by the project owner after the
existing public ELKS port was found. An invitation for ghaerr is deferred until
a first viable release candidate is ready for independent testing.

## License and provenance

Inherited code retains the upstream [LICENSE](LICENSE). New feasibility code is
MIT licensed under [feasibility/LICENSE](feasibility/LICENSE); new regression
tests use [tests/LICENSE](tests/LICENSE). Other third-party
licenses are described in [THIRD_PARTY](THIRD_PARTY.md). Development uses AI
coding assistance. Test results distinguish host, emulator and real hardware.
