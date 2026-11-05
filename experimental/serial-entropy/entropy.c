/* MIT. Experimental transport, not an RNG or authenticated network protocol.
 * A host-issued public session ID plus a shared counter binds each response.
 * Launching requires a fresh one-use session file. Never auto-start this build.
 */
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <stdio.h>
#include "entropy.h"
#ifndef ELKSSH_ENTROPY_DEVICE
#define ELKSSH_ENTROPY_DEVICE "/dev/ttyS0"
#endif
#ifndef ELKSSH_ENTROPY_DIR
#define ELKSSH_ENTROPY_DIR "/root/ssh1105"
#endif
#define SESSION ELKSSH_ENTROPY_DIR "/esession"
#define COUNTER ELKSSH_ENTROPY_DIR "/ecounter"
static unsigned char session[16];
static int ready, poisoned;
static void wipe(void *p, unsigned n) {
    volatile unsigned char *v = p;
    while (n--) *v++ = 0;
}
/* CRC-32/ISO-HDLC detects serial corruption; it is not authentication. */
static uint32_t checksum(const unsigned char *p, unsigned n) {
    uint32_t crc=UINT32_MAX;
    unsigned i;
    while (n--) {
        crc ^= *p++;
        for (i=0;i<8;i++) crc=(crc>>1)^((0UL-(crc&1UL))&UINT32_C(0xedb88320));
    }
    return crc^UINT32_MAX;
}
static int protected_file(int fd, unsigned length) {
    struct stat st;
    return fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_uid == 0
        && (st.st_mode & 077) == 0 && st.st_nlink == 1 && st.st_size == length;
}
static int exact(int fd, unsigned char *p, unsigned len, int writing, time_t end) {
    while (len) {
        fd_set fds;
        struct timeval wait;
        int n;
        if (time(NULL) >= end) { errno = EIO; return -1; }
        FD_ZERO(&fds); FD_SET(fd, &fds);
        wait.tv_sec = 1; wait.tv_usec = 0;
        n = select(fd+1, writing ? 0 : &fds, writing ? &fds : 0, 0, &wait);
        if (n < 0 && errno != EINTR) return -1;
        if (n <= 0) continue;
        n = writing ? write(fd,p,len) : read(fd,p,len);
        if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (n <= 0) { errno = EIO; return -1; }
        p += n; len -= n;
    }
    return 0;
}
ssize_t elkssh_serial_getrandom(void *out, size_t size, unsigned int flags) {
    unsigned char request[24], response[60], state[20];
    struct termios tty, previous;
    struct stat device;
    uint32_t seq;
    int fd=-1, file=-1, n, saved=EIO, changed=0;
    time_t end;
    (void)flags;
    if (poisoned || size != 32) { errno=EIO; return -1; }
    /* Serial O_EXCL serializes cooperating forked consumers. Administrative
     * ownership must also exclude consoles and other nonexclusive openers. */
    fd=open(ELKSSH_ENTROPY_DEVICE,O_RDWR|O_NOCTTY|O_NONBLOCK|O_EXCL);
    if (fd<0) goto fail;
    if (fstat(fd,&device)<0 || !S_ISCHR(device.st_mode) || device.st_uid!=0
            || (device.st_mode&077)!=0) goto fail;
    if (!ready) {
        file=open(SESSION,O_RDONLY);
        if (file<0 || !protected_file(file,16) || read(file,session,16)!=16) goto fail;
        close(file); file=-1;
        if (unlink(SESSION)<0) goto fail;
        sync();
        ready=1;
    }
    file=open(COUNTER,O_RDWR);
    if (file<0 || !protected_file(file,20) || read(file,state,20)!=20) goto fail;
    if (memcmp(state,session,16)) goto fail;
    seq=((uint32_t)state[16]<<24)|((uint32_t)state[17]<<16)|((uint32_t)state[18]<<8)|state[19];
    if (seq==UINT32_MAX) goto fail;
    seq++;
    state[16]=seq>>24; state[17]=seq>>16; state[18]=seq>>8; state[19]=seq;
    /* Reserve before sending. Interrupted requests are never reused. No
     * power-loss recovery is promised: every launch needs a fresh host session. */
    if (lseek(file,16,SEEK_SET)!=16 || write(file,state+16,4)!=4) goto fail;
    close(file); file=-1;
    if (tcgetattr(fd,&previous)<0) goto fail;
    tty=previous;
    tty.c_iflag=0; tty.c_oflag=0; tty.c_lflag=0;
    tty.c_cflag=CS8|CLOCAL|CREAD;
    tty.c_cc[VMIN]=1; tty.c_cc[VTIME]=0;
    if (cfsetispeed(&tty,B9600)<0 || cfsetospeed(&tty,B9600)<0) goto fail;
    if (tcsetattr(fd,TCSANOW,&tty)<0) goto fail;
    changed=1;
    for (n=0;n<8;n++) {
        int count=read(fd,response,sizeof(response));
        if (!count || (count<0 && errno==EAGAIN)) break;
        if (count<0) goto fail;
    }
    if (n==8) goto fail;
    memcpy(request,"ESQ1",4); memcpy(request+4,state,20);
    end=time(NULL)+10;
    if (exact(fd,request,sizeof(request),1,end)<0 || exact(fd,response,sizeof(response),0,end)<0) goto fail;
    if (memcmp(response,"ESR1",4) || memcmp(response+4,state,20)) goto fail;
    if (checksum(response,56)!=(((uint32_t)response[56]<<24)|((uint32_t)response[57]<<16)|((uint32_t)response[58]<<8)|response[59])) goto fail;
    /* Restore settings before exposing any seed bytes to the caller. */
    if (tcsetattr(fd,TCSANOW,&previous)<0) goto fail;
    changed=0;
    memcpy(out,response+24,32);
    wipe(response,sizeof(response)); wipe(request,sizeof(request)); wipe(state,sizeof(state));
    close(fd);
    return 32;
fail:
    if (errno) saved=errno;
    poisoned=1;
    if (file>=0) close(file);
    if (changed) tcsetattr(fd,TCSANOW,&previous);
    if (fd>=0) close(fd);
    wipe(response,sizeof(response)); wipe(request,sizeof(request)); wipe(state,sizeof(state));
    errno=saved;
    return -1;
}
