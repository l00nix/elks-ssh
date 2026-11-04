# HP signal callback layout — 2026-11-04

The HP release's signal validation uses a 16-bit byte count for a combined
near/far code allocation. The daemon exceeds 64 KiB of code, so that count
wraps and rejects libc's callback near the end of the first code segment.
Small registration probes do not expose this problem.

The retained HP 4.0 local kernel image has SHA-256
`55a2259accfaad7ff5a51fff9ec85127d1d10f94ae6ac0cfd3e22f0b93fceb56`,
matching the local boot-kit artifact. Its retained build source contains the
old `sys_signal` range check and allocates near/far code together. The running
HP reports `hp200lx-4.0-local 2026-10-21`; its in-memory kernel was not dumped.
The hardware comparisons below independently test the predicted behavior.

Upstream changed this validation in commit
[`7da0f265`](https://github.com/ghaerr/elks/commit/7da0f265c9dafb9eed87963dd4eae3180b0eeae2)
to compare paragraph ranges without truncating the allocation to 16-bit bytes.
The prepared QEMU kernel includes that fix. No kernel or libc was modified for
this SSH investigation.

## Controlled comparison

All layout probes use the medium memory model, the same signal-registration
source and the same toolchain/libc. Unexecuted NOP padding changes code size;
extracting the stock `signalcb.o` and linking it first changes callback position.
Each registers/restores SIGINT, SIGTERM, SIGPIPE, SIGCHLD and SIGSEGV, with both
ignore dispositions and custom handlers. They send no signals.

| Probe | Allocated code | Callback offset | Old byte-range limit | QEMU | HP |
| --- | ---: | ---: | ---: | --- | --- |
| `sig-near` | 52,720 | 50,314 | 52,720 | Pass | Pass |
| `sig-large` | 82,720 | 50,314 | 17,184 | Pass | All five custom handlers rejected, errno 22 |
| `sig-early` | 82,720 | 44 | 17,184 | Pass | Pass |

The first row rules out a simple signed 32-KiB address limit. The second adds
only far-code padding; ignore dispositions still work on the HP. The third
keeps the large allocation and moves the unchanged callback to its beginning.

## Application build adaptation

`Makefile.elks` resolves the medium-model libc selected by the compiler,
extracts its unchanged `signalcb.o`, and links that object before application
objects. The archive supplies the remaining libc functions normally. The
callback is refreshed on every link so changing toolchains cannot silently
reuse another libc's callback. Failed extraction stops the build.

For the normal daemon, code sizes remain 52,816 near + 26,656 far bytes. The
callback moves from offset 52,423 to 47, inside the older check's 13,936-byte
range. The client and QEMU test server use the same link rule. Signal errors
remain fatal; no registration, cleanup or entropy check is skipped.

This is a compatibility adaptation for the measured layouts. It is not a
universal repair for old kernels: for example, an allocation exactly divisible
by 64 KiB gives the old check a zero-byte range. Recheck code size, callback
placement and actual startup for every new candidate.

## Delivery and child cleanup

`sig-life` uses the large padding and early callback. It sends SIGUSR1 only to
itself and creates/waits for eight short-lived children. It checks all eight
notifications, exit statuses, and ECHILD after reaping. A ten-second alarm
bounds a stuck wait. Handlers only update native-word volatile counters.

ELKS resets caught signal dispositions after delivery. The probe reinstalls
them between iterations, as required by that API; the daemon already reinstalls
its SIGCHLD handler. An initial development probe assumed persistent handlers
and terminated on its second SIGUSR1 in QEMU. That fixture assumption was
corrected before any physical delivery test.

The corrected probe passes in both QEMU and on the physical HP:
`delivered=8 child_notifications=8 reaped=8`, `RESULT failures=0`, exit 0.
The HP returns to its shell with no remaining test process and about 397 KiB
free main memory. This validates the probe's delivery/reaping paths, not a
physical authenticated SSH session.

## Daemon validation

On the HP, the relinked normal daemon reports `Dropbear v2025.89`, then exits 1
with `Failure reading random device /dev/urandom`. Signal setup now succeeds;
the expected secure-randomness refusal is reached before key loading or listening.
`ps` shows no daemon left behind. The kernel, libc, boot and network configuration
remain unchanged; test files stay under `/root/sshprobe`.

The normal client, normal server and separate QEMU server all pass the linked
8086 instruction audit. The normal client/server still refuse missing entropy
in QEMU. All 11 cases of the combined QEMU 486/MINIX SSH suite pass: login,
wrong client key, wrong host key, unsafe authorization directory/file, output
stream, repeat login/exit status, stdin EOF, PTY commands, PTY input EOF and
forced rekeying. Connection children are reaped after every case. Rekey output
includes five NEWKEYS messages (initial exchange plus four rekeys).

The QEMU run samples maximum heap break 13,154 bytes and minimum SP-minus-break
6,774 bytes across 187 samples. These are not worst-case bounds. It uses fresh
host-fed test entropy, not a hardware entropy implementation. Input images remain
unchanged. No physical SSH login or original 8086/8088 execution is claimed.

Evidence: [physical HP results](evidence/20261104-signal-layout/result.json),
[HP serial transcript](evidence/20261104-signal-layout/serial.txt),
[artifact/layout hashes](evidence/20261104-signal-layout/artifacts.json),
[provenance](evidence/20261104-signal-layout/provenance.json),
[normal-build results](evidence/20261104-signal-layout/qemu-normal/result.json),
and [SSH regression results](evidence/20261104-signal-layout/qemu-ssh/result.json).

## Reproduction

Build with the existing prepared ELKS checkout:

```sh
ELKSSH_ELKS=/path/to/elks sh feasibility/toolchain/build-signal-layout.sh
python3 feasibility/tests/qemu_signal.py --image /path/to/hd32-fat.img \
    --build feasibility/build/signal-layout --out /path/to/results \
    --names sig-near sig-large sig-early sig-life
```

The build script retains ELF, map and disassembly, and runs the linked 8086
instruction audit for each fixture. QEMU uses a disposable image with no NIC.
Hardware testing uses checksummed serial transfers and separately records the
expected failing large/late-callback case. No test-only entropy adapter is
transferred to physical hardware.

Repeat the combined SSH regression with a separately built QEMU-only server:

```sh
make -f Makefile.elks PROGRAM=dropbear TEST_ENTROPY=1
python3 tests/qemu_ssh.py --image /path/to/hd32-minix14.img \
    --filesystem minix --mfs /path/to/mfs --server dropbear-qemu \
    --out /path/to/ssh-results --cpu 486 --suite --session-suite
```

The remote build host ran out of disk space during a duplicate probe build.
Removing only this run's already-retained generated disassemblies and archives
allowed the reproducibility check to finish. About 50 MiB remained afterward;
other projects' files were not removed.
