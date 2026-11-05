# Independent randomness: persistent-state checkpoint — 2026-11-05

The isolated persistent-state adapter passes **23 QEMU cases** and four public-
data exercises on the physical PPC. A separate storage probe passes nine QEMU
cases. This is a user-space experiment using BearSSL HMAC_DRBG; it is not yet
an SSH randomness source or a release candidate. At that isolated checkpoint the daemon and key utility
were not changed; later SSH integration is recorded in
[the persistent SSH checkpoint](PERSISTENT-SSH.md). No real secret seed or host key was provisioned on hardware.

## Design and tests

The [experimental design](../experimental/persistent-entropy/README.md) compares
storage approaches and defines the record and lock behavior. Each request loads
the current state under an exclusive lock and persists its successor before
releasing 32 bytes. A checksum detects accidental damage. A retained lock after
an uncertain operation refuses further use. No automatic fallback to an old
record is allowed. Independent Python `hashlib`/`hmac` code checks both output
and the full serialized state against the unchanged BearSSL implementation.

The storage experiment targets a preallocated MINIX block with QEMU `blkdebug`.
Final error rules explicitly specify `iotype = "write"`: reads remain enabled.
Both first-sector and second-sector write failures are tested with EIO and
ENOSPC. A failed second-sector write leaves a mixed record on the disk. The
application detects the difference by readback and refuses acknowledgement.
This strengthens the earlier source-only finding about `sync()`, but is still
specific to the tested BIOS/MINIX path. See the
[QEMU fault-injection documentation](https://www.qemu.org/docs/master/devel/testing/blkdebug.html)
and [I/O-type definition](https://qemu-project.gitlab.io/qemu/interop/qemu-qmp-ref.html#object-BlkdebugInjectErrorOptions).

| Persistent-adapter check | Result |
| --- | --- |
| Normal output and complete VM restart | Next output/state match the reference |
| Parent, child, then parent | Three distinct sequential outputs; restart advances again |
| Competing child while parent holds lock | Child refuses unchanged output; parent completes |
| Full filesystem | Preallocated state continues correctly; no new data block is needed for the empty lock file in this fixture |
| Insecure modes, missing file, busy lock, hard link, symbolic link | Refuse without changing caller output |
| Bad checksum, truncated state, exhausted counter | Refuse; process retry also refuses |
| Four targeted disk-error cases | Refuse output; removing the fault and rebooting still refuses the abandoned lock |
| Stops at transaction stages 1–5 | Reboot refuses the retained lock |
| Stop after durable state/unlock, before output | Reboot skips the unexposed output and uses the next state |

The full-filesystem case fills 29,715 KiB of guest data before `dd` reports
ENOSPC. It does not establish behavior with every inode or directory slot
exhausted. The nine separate storage cases cover healthy update, four reported
write errors, and four stops around write/sync/readback. QEMU disk caching is
explicitly **write-through**. Original input images are hash-verified unchanged.
All test state and displayed output are public and predictable.

## Physical PPC result

The PPC still reports vanilla ELKS 0.9.2 commit `e7a56a43`. Its root is MINIX
on `/dev/hda`, backed by a PicoMEM HDD image. Control and public-file transfer
used Ethernet Telnet/FTP at `10.0.0.66`; there was no serial entropy provider.

Single request, forked requests, overlapping-process rejection, and process
relaunch all passed. Six generated public vectors and the final state match
the independent reference. Wall times including Telnet overhead were 3.751,
6.208, 3.111 and 2.865 seconds respectively; these are not isolated CPU timings
or complete SSH performance measurements.

The files are confined to `/root/rngtest/rngprobe` and `/root/rngtest/state`.
The directory/binary are mode 700; the public state is mode 600. The final
generation is six. No lock or probe process remains, and a final `sync` was
issued. There is no SSH listener, automatic startup change, or firmware change.
The HP 200LX was not touched. A process relaunch is not a hardware reboot.

## Build identity and limits

The final probe SHA-256 is
`fd1134ac2356102187ede2f1f9d1e818c945424c85ed96d75a0c93f69e40edb2`.
Its linked static 8086 instruction audit passes: 11,984 bytes of code and
13,056 bytes of near-memory reservation before arguments/environment, including
an 8,192-byte stack. The adapter's compiler-reported frame is 2,338 bytes;
nested crypto/runtime frames add to that. This is not a whole-SSH stack bound
or a universal platform/CPU compatibility claim.

Evidence: [persistent matrix](evidence/20261105-persistent-state/persistent-summary.json),
[storage matrix](evidence/20261105-persistent-state/storage-summary.json),
[PPC results](evidence/20261105-persistent-state/ppc-result.json),
[linked audit](evidence/20261105-persistent-state/persistprobe-audit.json),
and [source hashes](evidence/20261105-persistent-state/sources.json).

```sh
ELKSSH_ELKS=/path/to/prepared/elks sh feasibility/toolchain/build-persistent.sh
python3 experimental/persistent-entropy/qemu_probe.py \
  --image /path/to/hd32-minix14.img --mfs feasibility/build/mfs \
  --probe feasibility/build/persistent/persistprobe \
  --out feasibility/test-output/persistent-matrix
```

## Next hardware gate

The owner has prepared a separate disposable ELKS MINIX **HDD image for
PicoMEM**. Do not treat the PPC as a CF-card machine or interrupt writes on its
working image. Use only the public fixture and coordinate power cuts at the
recorded transaction boundaries on this disposable image.
The tests must account for power reaching PicoMEM and its backing storage;
resetting the PPC CPU alone is not a storage power-loss test.

The unresolved assumption is acknowledged writes surviving power loss.
Readback can see data retained in a device/firmware cache; it is not a substitute
for that guarantee. Passing a finite power-cut test is evidence for the tested
configuration, not proof for every storage implementation. Storage behavior,
fresh secure provisioning, recovery tooling and complete SSH integration remain
release gates. Valid snapshots/clones cannot be detected by this local state:
restored/copied media must be securely reprovisioned before actual SSH use.

## Suggested entropyservice repository

The owner's [entropyservice reference](https://github.com/arussell/entropyservice)
collects bytes from another machine through SSH and supplies them to Linux's
kernel random pool with `rngd`. It is relevant to optional externally assisted
reseeding, but requires a helper and an already usable SSH client. It therefore
does not solve independent startup or provide the missing ELKS kernel random
interface. No code from that repository was imported or executed.

## Disposable PicoMEM image prepared

The owner booted a new vanilla ELKS image at `10.0.0.66`. Its version is again
0.9.2 commit `e7a56a43`, with the working `ne0=5,0x300,,0x92` setting. The only
network configuration change was `#net=ne0` to `net=ne0` in `/bootopts` (850
bytes afterwards). The original was saved at `/root/rngtest/bootopts.bak`;
FTP readback verified both files and `sync` completed. The inspected `rc.sys`
runs `net start $net`; existing `net.cfg` uses DHCP and starts Telnet/FTP.
Autostart is now boot-verified: after the physical power cycle, Ethernet was
reachable at the same address and `ps` showed `ktcp`, `telnetd` and `ftpd`
while the local console was still at `getty`.

The audited public probe and initial public state were installed under
`/root/rngtest` with modes 700 and 600 respectively. The first physical test
paused at **stage 6**, after state advancement/readback and lock removal, before
returning output. Host readback matched generation one of the independent
reference; no output was exposed.

The owner confirms that powering off the PPC also powered off PicoMEM, which
has no external power supply; its only attached USB device is a storage stick.
After this power cycle, generation one remained intact and the lock was absent.
A new request skipped the unexposed first output, returned the second reference
output and persisted generation two exactly. **Stage 6 recovery passed.** This
was a manually delayed power cut, not an interruption immediately after a device
acknowledgement, and does not establish a universal durability guarantee.

The second test paused at **stage 3**, after the state write/close returned
but before the application's explicit `sync()`. No output was exposed. After
the requested full power cycle, the advanced generation three record matched
the independent reference and the empty lock remained. The probe returned exit
1, left caller output unchanged, and refused a same-process retry. State and
lock were unchanged by the refusal. **Stage 3 recovery passed.** The record
survived despite pausing before explicit sync; this does not demonstrate a torn
write or mean that unflushed writes are always safe.

The interrupted state and lock remain on the PPC for inspection. Recovery must
use fresh secure provisioning while all consumers are stopped; deleting the
lock and reusing an uncertain record is not an accepted recovery procedure.
No firmware or SSH service changed.

Setup evidence: [configuration and backup hashes](evidence/20261105-picomem-power/setup.json),
[stage 6 armed state](evidence/20261105-picomem-power/armed-stage6.json), and
[stage 6 probe transcript](evidence/20261105-picomem-power/stage6-telnet.txt).
Recovery evidence: [stage 6 result](evidence/20261105-picomem-power/stage6-recovery.json),
[recovery transcript](evidence/20261105-picomem-power/stage6-recovery.txt), and
[boot processes](evidence/20261105-picomem-power/reboot-ps.txt).
Second test: [stage 3 armed state](evidence/20261105-picomem-power/armed-stage3.json)
and [pause transcript](evidence/20261105-picomem-power/stage3-telnet.txt).

Stage 3 recovery: [result](evidence/20261105-picomem-power/stage3-recovery.json),
[refusal transcript](evidence/20261105-picomem-power/stage3-recovery.txt),
[files](evidence/20261105-picomem-power/stage3-files.txt), and
[boot processes](evidence/20261105-picomem-power/stage3-reboot-ps.txt).

The next [provisioning checkpoint](PROVISIONING.md) tests host preparation and
fresh offline recovery in QEMU. It leaves this physical interrupted state intact.

On a separate `sshrec.img` prepared from the preserved interrupted image,
the first physical recovery request now matches the new public sequence and
persists generation one correctly. The original interrupted image is retained.
A power cycle of the recovered image now confirms that successful output
is not repeated; see the [recovery checkpoint](PROVISIONING.md).

The non-disclosing checker subsequently consumed recovery generation three on
the PPC. The [next checkpoint](PERSISTENT-SSH.md) passes eleven QEMU SSH/session
cases with freshly provisioned persistent state and prepares a separate private
hardware image; no public fixture becomes an SSH secret source.
