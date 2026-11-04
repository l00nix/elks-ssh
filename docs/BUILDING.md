# Building and testing

Use a prepared ELKS checkout with its IA16 compiler, libc and host tools.
The initial baseline is ELKS `e1469b64c5809c44d5c822eaeebd0e97d5996289`,
using `ia16-elf-gcc` 6.3.0. The checkout itself is not modified.

## Existing client

From the repository root:

```sh
ELKSSH_ELKS=/absolute/path/to/elks sh toolchain/build-external.sh
```

This builds `dbclient`, **not an ELKS sshd**. Strong random-device failure is
fatal. Do not re-enable the inherited weak-randomness option to make a login
demonstration work. A successful build is not a secure interoperability result.

The build script is suitable for a future `buildext.sh` entry. Image installation
through `elkscmd/ExtApplications` is deferred until a viable candidate exists;
no automatic startup service or package registration has been installed.

## Standalone feasibility probes

```sh
cd feasibility
sh tests/host.sh
ELKSSH_ELKS=/absolute/path/to/elks sh toolchain/build-external.sh
```

`build/cryptest` runs public X25519, SHA-256 and ChaCha20 vectors. `build/osprobe`
surveys existing sockets, PTYs, terminal settings, account lookup and the entropy
device path. It temporarily allocates/closes descriptors but does not bind,
connect, log in, modify accounts or generate keys.

The source uses 64-bit arithmetic implemented by the toolchain; it does not
assume a CPU with 64-bit registers. The probes use small-model code and data.

## Optional linked-code audit

Python is required only for development tools, not for the minimal ELKS build:

```sh
cd feasibility
ELKSSH_AUDIT=1 ELKSSH_ELKS=/absolute/path/to/elks sh toolchain/build-external.sh
export PATH=/absolute/path/to/elks/cross/bin:$PATH
for app in cryptest osprobe; do
    ia16-elf-objdump -d -z --insn-width=16 -M intel,i8086 \
        build/$app.elf > build/$app.dis
    python3 tools/isa-audit.py build/$app build/$app.elf build/$app.dis \
        --map build/$app.map --output build/$app-audit.json
done
```

The audit checks executable-section bytes, rejects later/unsupported opcodes,
and verifies that the inspected ELF text matches the converted executable.
It is a static gate, not proof of real 8086 execution or constant-time crypto.
Compiler `.su` files report individual frame bounds, not whole-call-chain peaks.

## QEMU

Install Python 3, `qemu-system-i386` and mtools. Supply a bootable, unpartitioned
ELKS FAT HD image with the normal network stack initially stopped:

```sh
cd feasibility
python3 tests/qemu_probe.py --image /path/to/hd32-fat.img \
    --cpu 486 --out test-output/qemu-486 --screenshot
python3 tests/qemu_probe.py --image /path/to/hd32-fat.img \
    --cpu pentium --out test-output/qemu-pentium
python3 tests/qemu_probe.py --image /path/to/hd32-fat.img \
    --cpu qemu32 --out test-output/qemu-client --client ../dbclient
```

Each run copies the input image, injects only the probes and serial boot option,
uses restricted user networking with no forwarded host ports, and checks that
the original image hash remains unchanged. Logs, binary hashes and a JSON result
are retained. `--screenshot` captures actual guest console pixels through QMP.
Do not use its wall-clock durations as 8086/8088 performance estimates.
The optional client check expects an image without a usable random device and
verifies that the client fails with an entropy error. It does not test a login.

## Remote compilation

The established remote ELKS build host can run the same scripts in a separate
project directory, using the prepared ELKS checkout read-only. Transfer source
and retrieve binaries, linked ELF/map/disassembly and logs. Keep credentials and
host-specific transport helpers outside this repository. Remote compilation and
the upstream build system's fetching of remote repositories are distinct steps.
