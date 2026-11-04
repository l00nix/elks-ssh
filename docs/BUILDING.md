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
QEMU test build completes public-key login and remote commands on a disposable
MINIX filesystem with host-fed entropy. It is not a production configuration.
The ELKS key-list basename is `authkeys` (default `~/.ssh/authkeys`); `-D`
changes its directory. Keep the directory owned by root/the intended user and
not group/other writable, with the key list a regular file owned by root/the
intended user and not group/other writable. The fixture uses modes 0700/0600.

With the prepared toolchain on PATH, build the development-only test executable:

```sh
make -f Makefile.elks wiretest iotest
```

Client and server links place the selected medium-model libc's unchanged
`signalcb.o` before application code. This avoids the HP 4.0 kernel's overflowing
signal-address range check for the measured layouts, without changing libc or
the kernel. Code-size and callback-position checks remain candidate-specific;
see [the signal-layout investigation and reproducer](SIGNAL-LAYOUT.md).

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

Separate medium-model X25519 comparisons, pinned BearSSL provenance and their
host/QEMU reproduction commands are in [X25519-COMPARISON](X25519-COMPARISON.md).
They do not change the daemon build. The smaller candidate currently fails its
target vectors; the comparison harness deliberately reports that failure.

## Optional linked-code audit

Python is required only for development tools, not for the minimal ELKS build:

```sh
cd feasibility
ELKSSH_AUDIT=1 ELKSSH_ELKS=/absolute/path/to/elks sh toolchain/build-external.sh
export PATH=/absolute/path/to/elks/cross/bin:$PATH
for app in cryptest osprobe; do
    ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 \
        build/$app.elf > build/$app.dis
    python3 tools/isa-audit.py build/$app build/$app.elf build/$app.dis \
        --map build/$app.map --output build/$app-audit.json
done
```

The audit checks executable-section bytes, rejects later/unsupported opcodes,
and verifies that the inspected ELF text matches the converted executable.
Medium-model daemon audits also compare `.fartext` against the converted
executable, using its 64-byte supplemental header. Use `objdump -D` to decode
across relocation symbols inside far-jump operands; `-d` can split a valid
instruction at such a symbol. Unexpected executable sections fail the mapping
check. It is a static gate, not proof of real 8086 execution or constant-time crypto.
Compiler `.su` files report individual frame bounds, not whole-call-chain peaks.

For the normal daemon, retain the linked ELF without changing the resulting
binary (run in the repository root with the prepared toolchain on PATH):

```sh
mkdir -p audit-tools
cp feasibility/tools/retain-elf2elks.py audit-tools/elf2elks
chmod +x audit-tools/elf2elks
export ELKSSH_REAL_ELF2ELKS=/absolute/path/to/elks/elks/tools/bin/elf2elks
export PATH="$PWD/audit-tools:$PATH"
make -f Makefile.elks PROGRAM=dropbear \
    CC="ia16-elf-gcc -Wl,-Map,dropbear-audit.map"
ia16-elf-objdump -D -z --insn-width=16 -M intel,i8086 \
    dropbear.elf > dropbear-audit.dis
python3 feasibility/tools/isa-audit.py dropbear dropbear.elf dropbear-audit.dis \
    --map dropbear-audit.map --output dropbear-audit.json
python3 feasibility/tests/isa_audit.py dropbear dropbear.elf \
    dropbear-audit.dis dropbear-audit.map
```

The regression script verifies exact-byte acceptance and rejection of altered
near/far code, missing far-code length and truncated payload/header. Retain binary
hashes with each report; an audit of one build does not cover later changes.

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

Both normal and QEMU server builds now reserve 16 KiB of heap by default; the
client retains 8 KiB. Both reserve an 8 KiB stack. `HEAP_SIZE` and `STACK_SIZE`
override link-time reservations and the main executable is relinked on each
build. Sampled server heap break grew to 13,154 bytes; these reservations and
samples are not a proven upper bound for authenticated sessions.
The I/O test also checks production address formatting for port 65535.

## Disposable MINIX login fixture

The FAT fixture cannot supply the ownership/modes required for public-key
authentication. Create a separate MINIX v1 image with 14-character names using
unmodified tools from the prepared ELKS checkout. Its existing kernel must have
MINIX support enabled; no kernel, libc or installed image is rebuilt or edited.
The conversion script is specific to this 32 MiB test fixture, not a general
filesystem migration tool. It assigns controlled root ownership/modes and
recreates device nodes from upstream `Make.devices`.

For example, build the host tools (not the target OS) and prepare the image:

```sh
export ELKSSH_TREE=/absolute/path/to/prepared/elks
mkdir -p feasibility/build feasibility/test-output/images
cc -O2 -o feasibility/build/mfs "$ELKSSH_TREE"/elks/tools/mfs/*.c
cc -O2 -o feasibility/build/setboot "$ELKSSH_TREE"/elks/tools/setboot/setboot.c
python3 tests/prepare_minix.py --fat-image /path/to/hd32-fat.img \
    --mfs feasibility/build/mfs --setboot feasibility/build/setboot \
    --devices "$ELKSSH_TREE/image/Make.devices" \
    --boot "$ELKSSH_TREE/bootblocks/minix.bin" \
    --out feasibility/test-output/images/hd32-minix.img
python3 tests/qemu_ssh.py --image feasibility/test-output/images/hd32-minix.img \
    --filesystem minix --mfs feasibility/build/mfs --server ./dropbear-qemu \
    --cpu pentium --suite --screenshot --out feasibility/test-output/login-suite
```

Use the paths to `Make.devices` and the prebuilt MINIX boot block in your prepared
tree; see the recorded hashes in [login evidence](LOGIN-PROGRESS.md). Each login
run copies the fixture, generates new keys, pins the host key, uses `/root/authkeys`
with `-D /root`, and destroys the temporary disk and private keys on completion.
The full suite additionally tests an occupied preauthentication slot, incorrect
keys, unsafe permissions, 16,144 bytes of output followed by a delayed marker,
repeat login, exit status 7 and connection-child cleanup. Omit `--suite` for the
basic login/delayed-output test. Run with `--entropy short` or `silent`, without
`--suite`/`--screenshot`, to test startup refusal on the same MINIX fixture.

Guest `ps` samples are retained in `memory.json`; they do not measure true peak
stack use or total system memory. QEMU wall time is not an 8088 benchmark.

Use `--session-suite` for additional stdin/EOF, PTY-command and forced-rekey
checks. It can be combined with `--suite` or run separately against the same
disposable fixture. The PTY tests run `tty`, `ps` and `cat /etc/issue`, requiring
both the beginning and final output markers. One keeps an 80x24 host terminal
open; the other supplies immediate SSH input EOF. The rekey case requests a
4 KiB client rekey limit, compares the entire payload and requires more than
one completed key exchange. These are automated command-session tests; terminal
resize, control-key delivery and a human-operated shell need separate validation.

## Experimental m15 daemon

See [M15-DAEMON](M15-DAEMON.md) for the isolated build overlay, probe commands,
malformed-KEX tests and current failures. It is not a deployment candidate.
