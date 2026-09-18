/*
 * TWRP for WSA — Boot Dispatcher
 *
 * Replaces /init in WSA's initrd.img. Kernel always starts at /init.
 * This binary IS /init after injection.
 *
 * Real WSA initrd structure:
 *
 *   NoGApps (2 files):
 *     /init       — 2MB ELF (full WSL init binary)
 *     /info.json
 *
 *   GApps/Magisk (12-16 files):
 *     /init       — SYMLINK -> lspinit
 *     /lspinit    — 430KB ELF (LSP init)
 *     /wsainit    — 2MB ELF (Magisk only)
 *     /info.json
 *     /overlay.d/sbin/* — GApps/Magisk images
 *
 * After TWRP injection:
 *     /init       — THIS dispatcher (replaces original)
 *     /init_orig  — original /init (symlink target or ELF)
 *     /sbin/twrp  — TWRP recovery binary
 *     /info.json  — metadata with recovery_flag
 *
 * Boot chain:
 *   Kernel -> /init (this dispatcher)
 *     -> recovery_flag true  -> exec /sbin/twrp (recovery)
 *     -> recovery_flag false -> exec /init_orig (normal Android)
 */

#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <ctype.h>

#define INFO_JSON   "/info.json"
#define TWRP_BIN    "/sbin/twrp"
#define INIT_ORIG   "/init_orig"

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

    execl(INIT_ORIG, "init_orig", NULL);

    return 1;
}
