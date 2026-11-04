# Building and testing

Use a prepared ELKS checkout with its IA16 compiler, libc and host tools.
The initial baseline is ELKS `e1469b64c5809c44d5c822eaeebd0e97d5996289`,
using `ia16-elf-gcc` 6.3.0. The checkout itself is not modified.

## Existing client

From the repository root:

```sh
ELKSSH_ELKS=/absolute/path/to/elks sh toolchain/build-external.sh
```

This builds the experimental `dbclient`. Strong random-device failure is
fatal. Do not re-enable the inherited weak-randomness option to make a login
demonstration work. A successful build is not a secure interoperability result.

The build script is suitable for a future `buildext.sh` entry. Image installation
through `elkscmd/ExtApplications` is deferred until a viable candidate exists;
no automatic startup service or package registration has been installed.

## Experimental server and wire regression

```sh
ELKSSH_PROGRAM=dropbear ELKSSH_ELKS=/absolute/path/to/elks sh toolchain/build-external.sh
```

This builds `dropbear` with the existing ELKS APIs. It is not ready for deployment
or automatic startup. The current image has no usable secure RNG; startup must
fail before binding a port. The configuration is single-user and public-key-only;
the normal build has no secure entropy source on the test image. The separate
QEMU test build reaches encrypted authentication but does not yet log in.

With the prepared toolchain on PATH, build the development-only test executable:

```sh
make -f Makefile.elks wiretest iotest
```

Client and server object directories are separate, and header changes trigger
recompilation. Integer-overflow, incompatible-pointer and implicit-declaration
warnings are build errors. Other warnings are retained in the evidence.

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
verifies that the client fails with an entropy error. The server check exercises
`dropbear -V` and foreground startup (`-F`), requiring refusal for missing
entropy. Syslog is disabled, so this build does not accept `-E`.

From the repository root, run the combined suite:

```sh
python3 feasibility/tests/qemu_probe.py --image /path/to/hd32-fat.img \
    --build feasibility/build --cpu 486 --out feasibility/test-output/server \
    --wiretest ./wiretest --client ./dbclient --server ./dropbear --iotest ./iotest
```

The checked-in cipher fixtures need no Python crypto dependency at test time.
To reproduce them independently, run `python3 tests/reference_vectors.py` in a
host environment with `cryptography` installed (validated with 50.0.2). This
host tool is not part of the ELKS build or entropy provisioning.

## Remote compilation

The established remote ELKS build host can run the same scripts in a separate
project directory, using the prepared ELKS checkout read-only. Transfer source
and retrieve binaries, linked ELF/map/disassembly and logs. Keep credentials and
host-specific transport helpers outside this repository. Remote compilation and
the upstream build system's fetching of remote repositories are distinct steps.

## QEMU-only entropy and SSH interoperability harness

This is development infrastructure, not a hardware installation procedure.
With the prepared toolchain on PATH:

```sh
make -f Makefile.elks PROGRAM=dropbear TEST_ENTROPY=1 HEAP_SIZE=16384
python3 tests/qemu_ssh.py --image /path/to/hd32-fat.img \
    --server ./dropbear-qemu --entropy short --out feasibility/test-output/short
python3 tests/qemu_ssh.py --image /path/to/hd32-fat.img \
    --server ./dropbear-qemu --entropy silent --out feasibility/test-output/silent
python3 tests/qemu_ssh.py --image /path/to/hd32-fat.img \
    --server ./dropbear-qemu --entropy healthy --out feasibility/test-output/ssh
```

The host needs OpenSSH and Python `cryptography` (tested with 50.0.2), plus QEMU
and mtools. A healthy entropy source does not imply a successful SSH test:
`status: blocked` and nonzero exit mean that login did not complete. The harness
records the client diagnostics and guest log without retaining secret keys or
entropy bytes. Its known-hosts file is pre-pinned and strict checking stays on.
See [the adapter's trust limits](ENTROPY.md#development-only-qemu-adapter).

`iotest` checks that a 40,000-byte request is capped at `INT_MAX` before a
mock callback returns EOF without accessing the buffer. A second case transfers
2048 bytes through interrupted and partial reads. Both use production `atomicio`
on the signed 16-bit ABI; neither measures whole-session memory usage.

The QEMU command above explicitly reserves 16 KiB of heap for investigation;
the normal default remains 8 KiB, with an 8 KiB stack. `HEAP_SIZE` and
`STACK_SIZE` override link-time reservations and the main executable is relinked
on each build. The observed 8 KiB key-exchange allocation failure motivated the
larger experiment; this is not a measured upper bound for authenticated sessions.
The I/O test also checks production address formatting for port 65535.
