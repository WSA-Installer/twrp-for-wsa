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
 *
 * Debug log:
 *   Written to /tmp/twrp_debug.log (ramdisk)
 *   Also tries Windows temp via /mnt/c if available
 */

#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <ctype.h>
#include <stdio.h>

#define INFO_JSON       "/info.json"
#define TWRP_BIN        "/sbin/twrp"
#define INIT_ORIG       "/init_orig"
#define LOG_RAMDISK     "/tmp/twrp_debug.log"
#define LOG_WIN_TEMP    "/mnt/c/Users/CYBERBU~1/AppData/Local/Temp/twrp_debug.log"

static int log_fd = -1;

static void log_open(void) {
    log_fd = open(LOG_RAMDISK, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (log_fd >= 0) {
        const char *header = "=== TWRP Dispatcher Debug Log ===\n";
        write(log_fd, header, strlen(header));
    }
    int win_fd = open(LOG_WIN_TEMP, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (win_fd >= 0) {
        const char *header = "=== TWRP Dispatcher Debug Log ===\n";
        write(win_fd, header, strlen(header));
        close(win_fd);
    }
}

static void log_msg(const char *msg) {
    if (log_fd >= 0) {
        write(log_fd, msg, strlen(msg));
        write(log_fd, "\n", 1);
    }
    int win_fd = open(LOG_WIN_TEMP, O_WRONLY | O_APPEND, 0644);
    if (win_fd >= 0) {
        write(win_fd, msg, strlen(msg));
        write(win_fd, "\n", 1);
        close(win_fd);
    }
}

static void log_close(void) {
    if (log_fd >= 0) {
        close(log_fd);
        log_fd = -1;
    }
}

static int read_file(const char *path, char *buf, int bufsize) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        log_msg("  read_file: FAILED to open");
        return -1;
    }
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

static void log_hex_path(const char *path, char *buf, int len) {
    char tmp[256];
    snprintf(tmp, sizeof(tmp), "  Path: %s", path);
    log_msg(tmp);
    if (len < 0) {
        log_msg("  Status: NOT FOUND");
    } else {
        char msg[64];
        snprintf(msg, sizeof(msg), "  Status: found (%d bytes)", len);
        log_msg(msg);
    }
}

int main(void) {
    log_open();
    log_msg("--- Dispatcher started ---");

    char buf[1024];
    int n = read_file(INFO_JSON, buf, sizeof(buf));

    if (n < 0) {
        log_msg("ERROR: /info.json not found or empty");
        log_msg("Falling back to /init_orig");
        log_close();
        execl(INIT_ORIG, "init_orig", NULL);
        return 1;
    }

    log_hex_path(INFO_JSON, buf, n);
    log_msg("  Checking recovery_flag...");

    if (cistrstr(buf, "\"recovery_flag\": \"true\"")) {
        log_msg("  recovery_flag = true");
        log_msg("  Launching /sbin/twrp");
        log_close();
        execl(TWRP_BIN, "twrp", NULL);
        log_msg("ERROR: exec /sbin/twrp FAILED");
    } else {
        log_msg("  recovery_flag = false or missing");
        log_msg("  Falling back to /init_orig");
        log_close();
        execl(INIT_ORIG, "init_orig", NULL);
    }

    log_msg("ERROR: exec failed, nothing to run");
    log_close();
    return 1;
}
