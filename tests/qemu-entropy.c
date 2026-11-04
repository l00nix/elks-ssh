/* MIT. Fresh host entropy over QEMU's private second serial channel.
 * This is an emulator test adapter, not a hardware entropy driver or libc API.
 * EGD blocking-read framing: two request bytes {2,32}, exactly 32 reply bytes.
 * Both getrandom flag modes use the same bounded exchange in this test build.
 */
#include "includes.h"
#include "qemu-entropy.h"

ssize_t elkssh_qemu_getrandom(void *buffer, size_t size, unsigned int flags) {
    const unsigned char request[2] = {2, 32};
    unsigned char bytes[32];
    struct termios tty;
    size_t received = 0;
    int fd, n, saved;
    const char *stage = "termios read";
    time_t deadline;
    (void)flags;
    if (size != sizeof(bytes)) { errno = EINVAL; return -1; }
    fd = open("/dev/ttyS1", O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) { perror("QEMU entropy open"); return -1; }
    if (tcgetattr(fd, &tty) < 0) goto fail;
    /* The prepared libc declares cfmakeraw but does not link it. */
    tty.c_iflag = 0; tty.c_oflag = 0; tty.c_lflag = 0;
    tty.c_cflag = CS8 | CLOCAL | CREAD;
    tty.c_cc[VMIN] = 1; tty.c_cc[VTIME] = 0;
    stage = "baud";
    if (cfsetispeed(&tty, B115200) < 0 || cfsetospeed(&tty, B115200) < 0) goto fail;
    stage = "termios write";
    if (tcsetattr(fd, TCSANOW, &tty) < 0) goto fail;
    /* TCFLSH is rejected by this ELKS serial driver. Drain the nonblocking
     * fd explicitly; the private host endpoint only sends on request. */
    stage = "drain";
    for (n = 0; n < 8; n++) {
        int drained = read(fd, bytes, sizeof(bytes));
        if (drained == 0 || (drained < 0 && errno == EAGAIN)) break;
        if (drained < 0) goto fail;
    }
    if (n == 8) { errno = EIO; goto fail; }
    stage = "request";
    if (write(fd, request, sizeof(request)) != sizeof(request)) { errno = EIO; goto fail; }
    deadline = time(NULL) + 5;
    stage = "response";
    while (received < sizeof(bytes)) {
        fd_set fds;
        struct timeval wait;
        if (time(NULL) >= deadline) { errno = EIO; goto fail; }
        FD_ZERO(&fds); FD_SET(fd, &fds);
        wait.tv_sec = 1; wait.tv_usec = 0;
        n = select(fd+1, &fds, NULL, NULL, &wait);
        if (n < 0 && errno != EINTR) goto fail;
        if (n <= 0) continue;
        n = read(fd, bytes+received, sizeof(bytes)-received);
        if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (n <= 0) { errno = EIO; goto fail; }
        received += n;
    }
    memcpy(buffer, bytes, sizeof(bytes));
    memset(bytes, 0, sizeof(bytes));
    close(fd);
    return size;
fail:
    saved = errno;
    fprintf(stderr, "QEMU entropy %s failed: %d\n", stage, saved);
    memset(bytes, 0, sizeof(bytes));
    close(fd);
    errno = saved;
    return -1;
}
