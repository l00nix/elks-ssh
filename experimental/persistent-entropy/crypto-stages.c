/* MIT. Isolated diagnostic wrapper around unchanged crypto implementations.
 * Print only fixed stage labels, process IDs and whole-second durations.
 * Never inspect or print keys, scalars, messages, signatures or random bytes.
 */
#ifndef ELKSSH_STAGE_DIAGNOSTICS
#error This file is restricted to the diagnostic build
#endif
#include "includes.h"
#include "dbutil.h"
#include "curve25519.h"
#ifdef ELKSSH_TRACE_EDCOMPACT
#include "experimental/edcompact/adapter.h"
#endif
#ifdef ELKSSH_TRACE_M15
void elkssh_m15_scalarmult(unsigned char *, const unsigned char *, const unsigned char *);
#endif

static time_t begin(const char *stage)
{
    fprintf(stderr, "CRYPTO pid=%u %s begin\n", (unsigned)getpid(), stage);
    fflush(stderr);
    return monotonic_now();
}

static void end(const char *stage, time_t started)
{
    fprintf(stderr, "CRYPTO pid=%u %s end seconds=%lu\n",
            (unsigned)getpid(), stage,
            (unsigned long)(monotonic_now() - started));
    fflush(stderr);
}

void elkssh_trace_x25519(unsigned char *q, const unsigned char *n,
                        const unsigned char *p)
{
    time_t started = begin("x25519");
#ifdef ELKSSH_TRACE_M15
    elkssh_m15_scalarmult(q, n, p);
#else
    dropbear_curve25519_scalarmult(q, n, p);
#endif
    end("x25519", started);
}

void elkssh_trace_sign(const unsigned char *m, unsigned long mlen,
                      unsigned char *s, unsigned long *slen,
                      const unsigned char *sk, const unsigned char *pk)
{
    time_t started = begin("ed25519-sign");
#ifdef ELKSSH_TRACE_EDCOMPACT
    if (elkssh_edcompact_sign(s, pk, sk, m, mlen) != 0)
        dropbear_exit("Experimental Ed25519 input refused");
    *slen = 64;
#else
    dropbear_ed25519_sign(m, mlen, s, slen, sk, pk);
#endif
    end("ed25519-sign", started);
}

int elkssh_trace_verify(const unsigned char *m, unsigned long mlen,
                       const unsigned char *s, unsigned long slen,
                       const unsigned char *pk)
{
    int result;
    time_t started = begin("ed25519-verify");
#ifdef ELKSSH_TRACE_EDCOMPACT
    result = elkssh_edcompact_verify(s, slen, pk, m, mlen);
#else
    result = dropbear_ed25519_verify(m, mlen, s, slen, pk);
#endif
    end("ed25519-verify", started);
    return result;
}
