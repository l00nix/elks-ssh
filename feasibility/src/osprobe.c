/* MIT. Read-only capability survey plus temporary socket/PTY allocation. */
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <pwd.h>
#include <termios.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/utsname.h>

int main(void)
{
	struct utsname u;
	struct passwd *pw;
	struct termios tio;
	char path[12];
	int fd, i, found = 0;

	puts("ELKS SSH OS feasibility 0.0.1 (not a server)");
	if (uname(&u) == 0)
		printf("Kernel: %s %s %s %s\n", u.sysname, u.release,
		       u.version, u.machine);
	fd = socket(AF_INET, SOCK_STREAM, 0);
	if (fd < 0) printf("TCP socket: unavailable errno=%d (%s)\n",
			   errno, strerror(errno));
	else {
		puts("TCP socket: allocated and closed; no bind/connect");
		close(fd);
	}
	for (i = 0; i < 4; i++) {
		sprintf(path, "/dev/ptyp%d", i);
		fd = open(path, O_RDWR);
		if (fd < 0) continue;
		printf("PTY: %s allocated and closed\n", path);
		close(fd);
		found = 1;
		break;
	}
	if (!found) puts("PTY: unavailable (missing or busy)");
	printf("Terminal settings: %s\n",
	       tcgetattr(STDIN_FILENO, &tio) == 0 ? "available" : "unavailable");
	pw = getpwuid(getuid());
	printf("Current account lookup: %s\n", pw ? "available" : "unavailable");
	fd = open("/dev/urandom", O_RDONLY | O_NONBLOCK);
	if (fd < 0) puts("Entropy device: absent/unavailable; secure RNG unresolved");
	else {
		puts("Entropy path opens; quality and semantics NOT established");
		close(fd);
	}
	puts("Survey complete; no login, identity change or network traffic.");
	return 0;
}
