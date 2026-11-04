/* Taken for Dropbear from OpenSSH 5.5p1 */

/*
 * Copyright (C) 2000-2003 Damien Miller.  All rights reserved.
 * Copyright (C) 1999 WIDE Project.  All rights reserved.
 * 
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the project nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE PROJECT AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE PROJECT OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */

/*
 * Pseudo-implementation of RFC2553 name / address resolution functions
 *
 * But these functions are not implemented correctly. The minimum subset
 * is implemented for ssh use only. For example, this routine assumes
 * that ai_family is AF_INET. Don't use it for another purpose.
 */

#include "includes.h"

#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#include <netinet/in.h>
#include <arpa/inet.h>

#ifndef AF_UNSPEC
#define AF_UNSPEC AF_INET
#endif

static int
elks_parse_service(const char *servname, long int *port)
{
	static const struct {
		const char *name;
		unsigned short port;
	} services[] = {
		{ "ssh", 22 },
		{ "telnet", 23 },
		{ "smtp", 25 },
		{ "domain", 53 },
		{ "http", 80 },
		{ "pop3", 110 },
		{ "imap", 143 },
		{ "https", 443 },
		{ NULL, 0 }
	};
	char *cp;
	size_t i;

	*port = 0;
	if (servname == NULL) {
		return 1;
	}

	*port = strtol(servname, &cp, 10);
	if (*port > 0 && *port <= 65535 && *cp == '\0') {
		*port = htons(*port);
		return 1;
	}

	for (i = 0; services[i].name != NULL; i++) {
		if (strcmp(servname, services[i].name) == 0) {
			*port = htons(services[i].port);
			return 1;
		}
	}

	return 0;
}

static int
elks_inet_aton(const char *hostname, struct in_addr *in)
{
	const char *p;
	int dots = 0;

	if (hostname == NULL || *hostname == '\0') {
		return 0;
	}

	for (p = hostname; *p; p++) {
		if (*p == '.') {
			dots++;
			continue;
		}
		if (!isdigit((unsigned char)*p)) {
			return 0;
		}
	}
	if (dots != 3) {
		return 0;
	}

	in->s_addr = in_aton(hostname);
	return 1;
}

#ifndef HAVE_GETNAMEINFO
int getnameinfo(const struct sockaddr *sa, size_t salen, char *host, 
                size_t hostlen, char *serv, size_t servlen, int flags)
{
	struct sockaddr_in *sin = (struct sockaddr_in *)sa;
	char tmpserv[16];

	if (sa->sa_family != AF_UNSPEC && sa->sa_family != AF_INET)
		return (EAI_FAMILY);
	if (serv != NULL) {
		snprintf(tmpserv, sizeof(tmpserv), "%u", (unsigned int)ntohs(sin->sin_port));
		if (strlcpy(serv, tmpserv, servlen) >= servlen)
			return (EAI_MEMORY);
	}

	if (host != NULL) {
		if ((flags & NI_NUMERICHOST) == 0 && (flags & NI_NAMEREQD)) {
			return (EAI_NODATA);
		}
		if (strlcpy(host, in_ntoa(sin->sin_addr.s_addr),
		    hostlen) >= hostlen)
			return (EAI_MEMORY);
	}
	return (0);
}
#endif /* !HAVE_GETNAMEINFO */

#ifndef HAVE_GAI_STRERROR
#ifdef HAVE_CONST_GAI_STRERROR_PROTO
const char *
#else
char *
#endif
gai_strerror(int err)
{
	switch (err) {
	case EAI_NODATA:
		return ("no address associated with name");
	case EAI_MEMORY:
		return ("memory allocation failure.");
	case EAI_NONAME:
		return ("nodename nor servname provided, or not known");
	case EAI_FAMILY:
		return ("ai_family not supported");
	default:
		return ("unknown/invalid error.");
	}
}    
#endif /* !HAVE_GAI_STRERROR */

#ifndef HAVE_FREEADDRINFO
void
freeaddrinfo(struct addrinfo *ai)
{
	struct addrinfo *next;

	for(; ai != NULL;) {
		next = ai->ai_next;
		free(ai);
		ai = next;
	}
}
#endif /* !HAVE_FREEADDRINFO */

#ifndef HAVE_GETADDRINFO
static struct
addrinfo *malloc_ai(int port, u_long addr, const struct addrinfo *hints)
{
	struct addrinfo *ai;

	ai = malloc(sizeof(*ai) + sizeof(struct sockaddr_in));
	if (ai == NULL)
		return (NULL);
	
	memset(ai, '\0', sizeof(*ai) + sizeof(struct sockaddr_in));
	
	ai->ai_addr = (struct sockaddr *)(ai + 1);
	/* XXX -- ssh doesn't use sa_len */
	ai->ai_addrlen = sizeof(struct sockaddr_in);
	ai->ai_addr->sa_family = ai->ai_family = AF_INET;

	((struct sockaddr_in *)(ai)->ai_addr)->sin_port = port;
	((struct sockaddr_in *)(ai)->ai_addr)->sin_addr.s_addr = addr;
	
	/* XXX: the following is not generally correct, but does what we want */
	if (hints->ai_socktype)
		ai->ai_socktype = hints->ai_socktype;
	else
		ai->ai_socktype = SOCK_STREAM;

	if (hints->ai_protocol)
		ai->ai_protocol = hints->ai_protocol;

	return (ai);
}

int
getaddrinfo(const char *hostname, const char *servname, 
    const struct addrinfo *hints, struct addrinfo **res)
{
	struct in_addr in;
	long int port;
	u_long addr;

	port = 0;
	*res = NULL;
	if (hints && hints->ai_family != AF_UNSPEC &&
	    hints->ai_family != AF_INET)
		return (EAI_FAMILY);
	if (servname != NULL) {
		if (!elks_parse_service(servname, &port))
			return (EAI_NONAME);
	}

	if (hints && hints->ai_flags & AI_PASSIVE) {
		addr = htonl(0x00000000);
		if (hostname && elks_inet_aton(hostname, &in) != 0)
			addr = in.s_addr;
		*res = malloc_ai(port, addr, hints);
		if (*res == NULL) 
			return (EAI_MEMORY);
		return (0);
	}
		
	if (!hostname) {
		*res = malloc_ai(port, htonl(0x7f000001), hints);
		if (*res == NULL) 
			return (EAI_MEMORY);
		return (0);
	}
	
	if (elks_inet_aton(hostname, &in)) {
		*res = malloc_ai(port, in.s_addr, hints);
		if (*res == NULL) 
			return (EAI_MEMORY);
		return (0);
	}
	
	/* Don't try DNS if AI_NUMERICHOST is set */
	if (hints && hints->ai_flags & AI_NUMERICHOST)
		return (EAI_NONAME);
	
	addr = in_gethostbyname(hostname);
	if (addr != 0) {
		*res = malloc_ai(port, addr, hints);
		if (*res == NULL) {
			return (EAI_MEMORY);
		}
		return (0);
	}
	
	return (EAI_NODATA);
}
#endif /* !HAVE_GETADDRINFO */
