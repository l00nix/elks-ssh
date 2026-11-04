/* MIT. Exercise production atomicio on the signed 16-bit ELKS ABI. */
#include "includes.h"
#include "atomicio.h"

static unsigned int calls, maximum, mode;
static ssize_t simulated_read(int fd, void *out, size_t length) {
    (void)fd;
    calls++;
    if (length > INT_MAX) { errno = EINVAL; return -1; }
    if (length > maximum) maximum = length;
    /* Boundary probe returns EOF before accessing the destination. */
    if (!mode) return 0;
    if (calls == 1) { errno = EINTR; return -1; }
    if (calls == 2 && length > 1024) length = 1024;
    memset(out, 0x5a, length);
    return (ssize_t)length;
}

int main(void) {
    static unsigned char data[2048];
    unsigned int i;
    size_t result;
    int fail = 0, ok;
    printf("ELKS I/O regression int=%u size_t=%u\n", (unsigned)sizeof(int), (unsigned)sizeof(size_t));
    /* No buffer access or pointer advance occurs: the callback returns EOF.
     * This isolates request-size conversion without a >PTRDIFF_MAX object. */
    result = atomicio(simulated_read, 0, data, 40000U);
    ok = result == 0 && errno == EPIPE && calls == 1 && maximum == INT_MAX;
    printf("%s signed-size cap and EOF largest=%u\n", ok ? "PASS" : "FAIL", maximum);
    if (!ok) fail = 1;
    mode = 1; calls = maximum = 0;
    result = atomicio(simulated_read, 0, data, sizeof(data));
    for (i = 0; i < sizeof(data) && data[i] == 0x5a; i++) {}
    ok = result == sizeof(data) && i == sizeof(data) && calls == 3;
    printf("%s interruption and short I/O bytes=%u calls=%u\n",
           ok ? "PASS" : "FAIL", (unsigned)result, calls);
    if (!ok) fail = 1;
    {
        struct sockaddr_in address;
        char port[8];
        memset(&address, 0, sizeof(address));
        address.sin_family = AF_INET;
        address.sin_port = htons(65535U);
        ok = getnameinfo((struct sockaddr *)&address, sizeof(address),
                        NULL, 0, port, sizeof(port), NI_NUMERICSERV) == 0
             && strcmp(port, "65535") == 0;
        printf("%s unsigned peer port 65535\n", ok ? "PASS" : "FAIL");
        if (!ok) fail = 1;
    }
    printf("RESULT %s I/O\n", fail ? "FAIL" : "PASS");
    return fail;
}
