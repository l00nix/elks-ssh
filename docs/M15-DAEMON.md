# Experimental m15 daemon integration — 2026-11-04

Later checkpoint: the [persistent-state diagnostic comparison](PPC-SSH-DIAGNOSTICS.md)
uses a small listener with Dropbear's existing inetd mode and passes all eleven
QEMU session cases. The earlier binaries and failures below remain historical
evidence; they are not the newly tested combination.

**Not a hardware candidate.** BearSSL m15 now links into an isolated Dropbear
server using the existing ELKS toolchain and medium-model linker script. The
normal daemon is unchanged. This experiment authenticates an OpenSSH client,
but shell execution fails with `ENOMEM`. Production entropy and target timing
security remain unresolved.

## What changed

`feasibility/toolchain/Makefile.m15` replaces only the X25519 call sites in
`kex-x25519.o`. Dropbear's protocol validation, authentication, Ed25519 and
entropy policy remain intact. Pinned BearSSL sources are unchanged. Outputs,
objects and the optional QEMU entropy adapter remain separate from normal builds.
An experimental `execv` wrapper reports the error number if shell execution fails.

The initial combined build overflowed the first 64 KiB code segment. Moving
BearSSL's large multiplication function into `.fartext.m15` makes both code
segments fit. The forced declaration must also use IA16's `far_section`
attribute: section placement alone linked and passed the ISA audit, but generated
incorrect cross-segment calls. That failed attempt is not a usable binary.
The corrected placement uses the stock linker script; no kernel, libc or
architecture changes were made.

## Results and limits

| Check | Result |
| --- | --- |
| Linked 8086 instruction audit | Both experimental daemon variants and both probes pass static checks |
| m15 daemon-object probe | All 12 public X25519 vectors pass in QEMU |
| Malformed SSH KEX | Zero, one and 31-byte public points rejected; children reaped |
| Modern client | OpenSSH 10.3p1 verifies the host, completes KEX and public-key authentication |
| Shell execution | Fails: diagnostic wrapper reports errno 12 (`ENOMEM`); no successful command session |
| Normal experimental build | Refuses startup without `/dev/urandom` |
| Ed25519 public RFC 8032 probe | One isolated run passes signing, verification, altered signature and short signature checks |
| Ed25519 repeat after m15 probe | Does not complete within the 300-second test window; unresolved ordering/runtime issue |
| Physical hardware | Not touched in this checkpoint |

The successful isolated Ed25519 run measured 13 guest seconds for signing,
26 for verification, 25 for rejecting an altered signature and zero for rejecting
a short signature. These are QEMU observations, not HP/8088 estimates. They are
not a reliable performance baseline while the combined-run failure remains
unexplained. The first combined run was interrupted; its repeat is retained as
failure evidence rather than discarded.

The final diagnostic QEMU binary has 54,928 bytes of first-segment code and
63,472 bytes of second-segment code, leaving only 2,064 bytes in the latter.
Its static data, BSS, heap reservation and stack reservation total 42,592 bytes
before arguments/environment. `ps` reports a 161,152-byte process size, which
must not be summed as if every process had private copies of all code.
Sampled connection heap reached 13,154 bytes; samples do not establish a peak
bound. The actual `execv` failure takes precedence over static fit checks.

The earlier candidate without the error wrapper also failed command execution.
Its full session suite stopped after the first command failure; subsequent
PTY, EOF and rekey checks were **not** run for this backend. Earlier passing
normal-daemon suites remain evidence for their own recorded binary hashes only.
Disposable FAT and MINIX input images were unchanged.

## Timing security gate

Inspection of the linked Ed25519 `__muldi3` helper finds conditional branches
on multiplication intermediates (carry handling). The helper is used by secret
signing arithmetic. Therefore the source's regular loops do not establish
constant-time execution on this toolchain. This is a concrete review blocker,
not a demonstrated remote key-recovery attack.

The m15 code also emits native 16-bit `MUL` operations. Its timing on the original
8086/8088 and the compiler's decomposition of wider operations still need
qualification. Enabling a BearSSL multiplication macro alone would not establish
that property. See BearSSL's [constant-time multiplication discussion](https://bearssl.org/ctmul.html).
Do not select this backend for production based only on speed or vector success.

## Reproduce

Use the prepared ELKS checkout and toolchain described in [BUILDING](BUILDING.md):

```sh
ELKSSH_ELKS=/path/to/prepared/elks sh feasibility/toolchain/build-m15-daemon.sh
python3 feasibility/tests/qemu_crypto_integration.py \
  --image /path/to/hd32-fat.img --build feasibility/build/m15-daemon \
  --out feasibility/test-output/m15-primitives
python3 tests/qemu_ssh.py --image /path/to/hd32-minix.img \
  --filesystem minix --mfs /path/to/mfs \
  --server feasibility/build/m15-daemon/dropbear-m15-qemu \
  --cpu 486 --suite --session-suite --kex-rejection-suite \
  --out feasibility/test-output/m15-ssh
```

The failures above are expected unresolved results, not successful release checks.
Use `--names edbench dropbear-m15` to reproduce the isolated probe order.
The Ed25519 fixture uses the public seed from [RFC 8032 test 1](https://www.rfc-editor.org/rfc/rfc8032.html#section-7.1);
its RNG stub aborts if accidentally invoked. Never install the QEMU binary.

Evidence is under [20261104-m15-daemon](evidence/20261104-m15-daemon/).
The next work is to isolate the order-dependent probe failure and reduce the
whole daemon's working memory/code cost while preserving secure process setup.
A reviewed target arithmetic path is required before production selection.
Hardware entropy and Mac/Windows hardware captures remain later gates.
