#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define INFO_JSON "/info.json"
#define TWRP_BIN  "/sbin/twrp"
#define LSPINIT   "/lspinit"
#define WSAINIT   "/wsainit"

static int read_file(const char *path, char *buf, int bufsize) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    int n = read(fd, buf, bufsize - 1);
    close(fd);
    if (n <= 0) return -1;
    buf[n] = 0;
    return n;
}

int main(void) {
    char buf[1024];
    if (read_file(INFO_JSON, buf, sizeof(buf)) > 0) {
        if (strstr(buf, "\"recovery_flag\": \"true\""))
            execl(TWRP_BIN, "twrp", NULL);
    }
    execl(LSPINIT, "lspinit", NULL);
    execl(WSAINIT, "wsainit", NULL);
    return 1;
}
