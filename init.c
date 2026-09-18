/*
 * TWRP for WSA — Boot Dispatcher
 *
 * Replaces /init in WSA's initrd.img. Reads /info.json to decide
 * whether to boot TWRP recovery or chain to the original init.
 *
 * Real WSA initrd structure (from actual images):
 *
 *   Type A — NoGApps (2MB initrd):
 *     /init       — 2MB ELF (full WSL init binary)
 *     /info.json  — metadata
 *
 *   Type B — GApps/Magisk (288MB initrd):
 *     /init       — SYMLINK -> "lspinit"
 *     /lspinit    — 430KB ELF (LSP init)
 *     /magiskinit — 278KB ELF (Magisk, if present)
 *     /wsainit    — 2MB ELF (original WSA init, Magisk only)
 *     /info.json  — metadata
 *     /overlay.d/sbin/* — GApps/Magisk images
 *
 * After TWRP injection:
 *   /init       — THIS dispatcher (replaces original symlink or ELF)
 *   /sbin/twrp  — TWRP recovery binary (injected)
 *   /info.json  — metadata with recovery_flag
 *   /lspinit    — preserved (GApps/Magisk only)
 *   /wsainit    — preserved (Magisk only)
 *
 * Boot chain:
 *   Recovery:  /init (this) -> read recovery_flag -> exec /sbin/twrp
 *   Normal:    /init (this) -> read recovery_flag -> exec /lspinit or /wsainit
 */

#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <ctype.h>

#define INFO_JSON   "/info.json"
#define TWRP_BIN    "/sbin/twrp"
#define LSPINIT     "/lspinit"
#define WSAINIT     "/wsainit"
#define INIT_ORIG   "/init.orig"

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

    /* Read recovery_flag from /info.json */
    if (read_file(INFO_JSON, buf, sizeof(buf)) > 0) {
        if (cistrstr(buf, "\"recovery_flag\": \"true\""))
            execl(TWRP_BIN, "twrp", NULL);
    }

    /*
     * Normal boot — chain to original init.
     *
     * GApps/Magisk images: /init was a symlink to "lspinit".
     *   The inject process preserves /lspinit, so exec it.
     *
     * Magisk images: also have /wsainit as fallback.
     *
     * NoGApps images: /init WAS the 2MB WSL init binary.
     *   The inject process should save it as /init.orig.
     */
    execl(LSPINIT, "lspinit", NULL);
    execl(WSAINIT, "wsainit", NULL);
    execl(INIT_ORIG, "init.orig", NULL);

    return 1;
}
