/* MIT. Experimental adapter; no entropy or key-generation interface. */
#ifndef ELKSSH_EDCOMPACT_H
#define ELKSSH_EDCOMPACT_H
#define ELKSSH_EDCOMPACT_MAX_MESSAGE 4096UL
int elkssh_edcompact_sign(unsigned char signature[64],
    const unsigned char public_key[32], const unsigned char seed[32],
    const unsigned char *message, unsigned long length);
int elkssh_edcompact_verify(const unsigned char *signature, unsigned long slen,
    const unsigned char public_key[32], const unsigned char *message,
    unsigned long length);
#endif
