#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <ctype.h>

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

static int cistrstr(const char *haystack, const char *needle) {
    if (!needle || !*needle) return 1;
    size_t nlen = strlen(needle);
    for (const char *p = haystack; *p; p++) {
        size_t i = 0;
        while (i < nlen && p[i] && tolower((unsigned char)p[i]) == tolower((unsigned char)needle[i]))
            i++;
        if (i == nlen) return 1;
    }
    return 0;
}

int main(void) {
    char buf[1024];
    if (read_file(INFO_JSON, buf, sizeof(buf)) > 0) {
        if (cistrstr(buf, "\"recovery_flag\": \"true\""))
            execl(TWRP_BIN, "twrp", NULL);
    }
    execl(LSPINIT, "lspinit", NULL);
    execl(WSAINIT, "wsainit", NULL);
    return 1;
}
