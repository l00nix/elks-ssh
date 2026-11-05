# Dedicated serial entropy experiment

This is an **assisted, controlled-cable prototype**, not a production entropy
service or an authenticated network protocol. It is isolated from the ordinary
Dropbear build. The Mac supplies OS random bytes over a dedicated physical
serial cable while Telnet provides separate test control. No kernel, libc or
firmware changes are required. Do not use this framing over an untrusted link.

The provider does not replace Dropbear's cryptography or PRNG. It supplies the
fresh 32-byte seeds requested by the existing PRNG. No seed bytes, fingerprints
of seeds, private keys or raw serial responses are written to logs. Public
session identifiers and counters are not entropy substitutes.

## Framing and state

All integers on the wire are big-endian. Each launch uses a newly generated
128-bit public session ID from the host OS RNG:

| Direction | Frame |
| --- | --- |
| ELKS request | `ESQ1`, session ID (16 bytes), counter (4 bytes) |
| Host response | `ESR1`, same ID/counter, fresh OS seed (32 bytes), CRC-32 (4 bytes) |

The response CRC is CRC-32/ISO-HDLC over its first 56 bytes. It detects serial
corruption; it does **not** authenticate a sender. The physical cable, host OS
and administrative control of both endpoints are the trust boundary.

`esession` contains the public 16-byte ID. `ecounter` contains that ID followed
by a 32-bit counter initially zero. ELKS requires root-owned regular files with
no group/other permissions and one link. The containing directory must also
be under trusted root control. The launch file is consumed and synced before
first use; forks inherit the ID, while each request reserves its next counter
in the shared counter file before transmitting. The serial `O_EXCL` open
serializes cooperating consumers. The adapter also requires a root-owned
character device without group/other permissions. Administrative ownership
must exclude consoles and nonexclusive readers, including other root programs.

Every response must match the session and reserved counter and pass its CRC.
Reads/writes have a ten-second exchange deadline. Bounded draining rejects an
unquiet input queue. Errors leave the caller's output untouched, erase local
response storage, and poison that process's adapter so a retry cannot consume
late bytes. The host rejects duplicate/backward counters and stops after 1,024
successful responses. It checks for repeated source output in memory only.
These are framing/state guards, not a statistical test of entropy quality.

A new process cannot relaunch from the consumed `esession`. Provider restart,
target reboot, failed provisioning or counter loss requires stopping the old
consumer and provisioning a **new** host-generated bootstrap pair. Never copy
or restore an old pair, update it under a running daemon, or configure this
build for automatic startup. Counter reservation is visible to other processes,
but power-loss durability and arbitrary disk snapshot rollback are not qualified.
The tested assisted launch procedure is not a standalone persistent-state RNG.

## Builds

From the repository root with the existing prepared ELKS toolchain:

```sh
ELKSSH_ELKS=/path/to/elks sh experimental/serial-entropy/build-probe.sh
ELKSSH_ELKS=/path/to/elks sh experimental/serial-entropy/build-server.sh
```

Outputs under `feasibility/build/serial-entropy` include linked ISA audits.
Hardware variants use `/dev/ttyS0`; emulator variants use `/dev/ttyS1`, both at
9600 8N1. State paths are `/root/ssh1105/esession` and `ecounter`.
The separate `dropbear-serial` build refuses all entropy failures without
falling back to a file and disables seed-file writeback. The ordinary server
retains its existing behavior and is not overwritten.

## Tests

```sh
python3 experimental/serial-entropy/test_provider.py
python3 experimental/serial-entropy/run_matrix.py \
  --image /path/to/hd32-minix.img --mfs /path/to/mfs \
  --probe feasibility/build/serial-entropy/eprobe-qemu \
  --out feasibility/test-output/serial-matrix
```

The matrix uses disposable images and private emulator sockets. It tests every
truncated frame length (0–59), corrupt/stale/replayed replies, source failure,
invalid state and permissions, an occupied port, forked requests and refusal
to relaunch without a fresh bootstrap. `qemu_probe.py --daemon` additionally
checks the daemon's startup path with a deliberately missing host key. It does
not perform authentication or a shell session.

Physical tests must first establish a separate control connection, verify the
probe hash and confirm the serial cable's identity and exclusive ownership.
`hardware_probe.py` operates only when given an explicit host/device and uses
an already staged probe. It changes serial permissions temporarily, preserves
the original mode on success, and consumes/removes its public state files.
If interrupted, inspect the target and restore the original device mode before
returning the port to normal use. No entropy service is left running.

The standalone provider starts a new session and creates a new local directory:

```sh
python3 experimental/serial-entropy/provider.py \
  --device /dev/cu.EXPLICIT_DEVICE --bootstrap /private/new-session-directory
```

After confirming no previous consumer is active, provision **only the public**
bootstrap files into the protected target directory, verify readback, set the
serial device and state files to mode 600, and launch the explicitly selected
probe or experimental daemon. Secret seeds travel only over serial. Host/client
SSH key provisioning is separate and is not performed by these tests.
