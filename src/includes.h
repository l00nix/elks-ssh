/*
 * Dropbear - a SSH2 server
 * 
 * Copyright (c) 2002,2003 Matt Johnston
 * All rights reserved.
 * 
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE. */

#ifndef DROPBEAR_INCLUDES_H_
#define DROPBEAR_INCLUDES_H_

#include "options.h"
#include "debug.h"

#include <sys/types.h>
#include <sys/ioctl.h>
#include <sys/param.h> /* required for BSD4_4 define */
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <sys/resource.h>

#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
#include <pwd.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>
#include <syslog.h>
#include <netdb.h>
#include <ctype.h>
#include <stdarg.h>
#include <dirent.h>
#include <time.h>
#include <setjmp.h>
#include <assert.h>

#ifdef __ia16__
#include <stdint.h>
typedef unsigned int u_int;
typedef unsigned long u_long;
typedef unsigned short u_short;
typedef unsigned char u_char;
typedef uint8_t u_int8_t;
typedef uint16_t u_int16_t;
typedef uint32_t u_int32_t;
typedef long suseconds_t;

struct timespec {
	time_t tv_sec;
	long tv_nsec;
};

struct iovec {
	void *iov_base;
	size_t iov_len;
};

#ifndef SHUT_RD
#define SHUT_RD   0
#define SHUT_WR   1
#define SHUT_RDWR 2
#endif

#ifndef SIGBUS
#define SIGBUS 0
#endif
#ifndef SIGFPE
#define SIGFPE 0
#endif
#ifndef SIGILL
#define SIGILL 0
#endif
#ifndef SIGTRAP
#define SIGTRAP 0
#endif

#ifndef AF_UNSPEC
#define AF_UNSPEC AF_INET
#endif
#ifndef PF_UNSPEC
#define PF_UNSPEC AF_UNSPEC
#endif
#ifndef AF_MAX
#define AF_MAX 255
#endif

#ifndef UIO_MAXIOV
#define UIO_MAXIOV 8
#endif

#ifndef IPPROTO_TCP
#define IPPROTO_TCP 6
#endif
#ifndef TCP_NODELAY
#define TCP_NODELAY 1
#endif

#ifndef HAVE_GETGROUPS
static inline int getgroups(int size, gid_t list[])
{
	(void)size;
	(void)list;
	errno = ENOSYS;
	return -1;
}
#endif

#ifndef HAVE_CLOCK
static inline clock_t clock(void)
{
	return (clock_t)time(NULL);
}
#endif
#endif

#ifdef HAVE_UTMP_H
#include <utmp.h>
#endif

#ifdef HAVE_UTMPX_H
#include <utmpx.h>
#endif

#ifdef HAVE_PATHS_H
#include <paths.h>
#endif

#ifdef HAVE_LASTLOG_H
#include <lastlog.h>
#endif

#ifdef HAVE_NETINET_IN_H
#include <netinet/in.h>
#endif

#include <arpa/inet.h>

/* netbsd 1.6 needs this to be included before netinet/ip.h for some
 * undocumented reason */
#ifdef HAVE_NETINET_IN_SYSTM_H
#include <netinet/in_systm.h>
#endif

#include <netinet/ip.h>

#ifdef HAVE_NETINET_TCP_H
#include <netinet/tcp.h>
#endif

#ifdef HAVE_INTTYPES_H
#include <inttypes.h>
#endif

#ifdef HAVE_LIBUTIL_H
#include <libutil.h>
#endif

#ifdef HAVE_CRYPT_H
#include <crypt.h>
#endif

#ifndef DISABLE_ZLIB
#include <zlib.h>
#endif

#ifdef HAVE_UTIL_H
#include <util.h>
#endif

#ifdef HAVE_SHADOW_H
#include <shadow.h>
#endif

#ifdef HAVE_LIBGEN_H
#include <libgen.h>
#endif

#ifdef HAVE_SYS_UIO_H
#include <sys/uio.h>
#endif

#ifdef HAVE_SYS_RANDOM_H
#include <sys/random.h>
#endif

#ifdef HAVE_SYS_PRCTL_H
#include <sys/prctl.h>
#endif

#ifdef HAVE_ENDIAN_H
#include <endian.h>
#endif

#ifdef HAVE_SYS_ENDIAN_H
#include <sys/endian.h>
#endif

#ifdef BUNDLED_LIBTOM
#include "../libtomcrypt/src/headers/tomcrypt.h"
#if DROPBEAR_NORMAL_DH || DROPBEAR_ECDH || DROPBEAR_RSA || DROPBEAR_DSS || DROPBEAR_ECDSA
#include "../libtommath/tommath.h"
#else
typedef struct {
	int unused;
} mp_int;
#endif
#else
#include <tomcrypt.h>
#if DROPBEAR_NORMAL_DH || DROPBEAR_ECDH || DROPBEAR_RSA || DROPBEAR_DSS || DROPBEAR_ECDSA
#include <tommath.h>
#else
typedef struct {
	int unused;
} mp_int;
#endif
#endif

#include "compat.h"

#ifndef HAVE_U_INT8_T
typedef unsigned char u_int8_t;
#endif /* HAVE_U_INT8_T */
#ifndef HAVE_UINT8_T
typedef u_int8_t uint8_t;
#endif /* HAVE_UINT8_T */

#ifndef HAVE_U_INT16_T
typedef unsigned short u_int16_t;
#endif /* HAVE_U_INT16_T */
#ifndef HAVE_UINT16_T
typedef u_int16_t uint16_t;
#endif /* HAVE_UINT16_T */

#ifndef HAVE_U_INT32_T
typedef unsigned int u_int32_t;
#endif /* HAVE_U_INT32_T */
#ifndef HAVE_UINT32_T
typedef u_int32_t uint32_t;
#endif /* HAVE_UINT32_T */

#ifndef SIZE_T_MAX
#define SIZE_T_MAX ((size_t)-1)
#endif /* SIZE_T_MAX */

#ifdef HAVE_LINUX_PKT_SCHED_H
#include <linux/types.h>
#include <linux/pkt_sched.h>
#endif

#if DROPBEAR_PLUGIN
#include <dlfcn.h>
#endif

extern char** environ;

#include "fake-rfc2553.h"

#include "fuzz.h"

#ifndef LOG_AUTHPRIV
#define LOG_AUTHPRIV LOG_AUTH
#endif

/* so we can avoid warnings about unused params (ie in signal handlers etc) */
#ifdef UNUSED 
#elif defined(__GNUC__) 
# define UNUSED(x) UNUSED_ ## x __attribute__((unused)) 
#elif defined(__LCLINT__) 
# define UNUSED(x) /*@unused@*/ x 
#else 
# define UNUSED(x) x 
#endif

/* static_assert() is a keyword in c23, earlier libc often supports
 * it as a macro in assert.h.
 * _Static_assert() is a keyword supported since c11.
 * If neither are available, do nothing */
#ifndef HAVE_STATIC_ASSERT
#ifdef HAVE_UNDERSCORE_STATIC_ASSERT
#define static_assert(condition, message) _Static_assert(condition, message)
#else
#define static_assert(condition, message)
#endif
#endif

#endif /* DROPBEAR_INCLUDES_H_ */
