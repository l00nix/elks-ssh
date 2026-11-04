/* MIT. Unexecuted NOP padding to reproduce large-code signal range checks.
 * This is a test fixture, never linked into the daemon.
 */
#ifndef NEAR_PAD
#define NEAR_PAD 50000
#endif
#ifndef FAR_PAD
#define FAR_PAD 30000
#endif
    .arch i8086, nojumps
    .code16
    .text
    .fill NEAR_PAD, 1, 0x90
    .section .fartext.f.sigpad,"ax",@progbits
    .fill FAR_PAD, 1, 0x90
