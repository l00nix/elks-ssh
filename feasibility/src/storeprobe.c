/* MIT. Public-pattern storage experiment only. Never writes RNG state. */
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned char data[1024], check[1024];
static unsigned int pause_at;

static void stage(unsigned int n)
{
    printf("STAGE %u\n", n);
    fflush(stdout);
    if (pause_at == n) {
        char c;
        if (read(0, &c, 1) != 1) _exit(90);
    }
}

int main(int argc, char **argv)
{
    int fd, n, closed;
    struct stat st;
    if (argc < 2 || argc > 3) return 2;
    pause_at = argc == 3 ? (unsigned int)atoi(argv[2]) : 0;
    memset(data, 'B', sizeof data);
    fd = open(argv[1], O_RDWR);
    if (fd < 0) { puts("REFUSED open"); return 10; }
    if (fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) || st.st_size != 1024) {
        close(fd); puts("REFUSED file"); return 11;
    }
    stage(1);
    n = write(fd, data, sizeof data);
    closed = close(fd);
    if (n != sizeof data || closed < 0) { puts("REFUSED write"); return 12; }
    stage(2);
    sync();
    stage(3);
    fd = open(argv[1], O_RDONLY);
    if (fd < 0) { puts("REFUSED reopen"); return 13; }
    n = read(fd, check, sizeof check);
    closed = close(fd);
    if (n != sizeof check || closed < 0 || memcmp(data, check, sizeof data)) {
        puts("REFUSED readback"); return 14;
    }
    stage(4);
    puts("ACKNOWLEDGED update");
    return 0;
}
