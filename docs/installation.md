# Installation Guide

Step-by-step instructions for installing TWRP recovery into WSA.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Download](#download)
- [Inject TWRP](#inject-twrp)
- [Enable TWRP Mode](#enable-twrp-mode)
- [Verify Installation](#verify-installation)
- [System Apps, Modules & Hook](#system-apps-modules--hook)
- [IMG Manager & .img Open With](#img-manager--img-open-with)
- [Reboot Back to Android](#reboot-back-to-android)
- [Restore Original initrd.img](#restore-original-initrdimg)
- [What's Next?](#whats-next)

---

## Prerequisites

Before installing TWRP for WSA, ensure you have:

| Requirement | Details |
|:------------|:--------|
| Windows 10/11 | Build 19041 or later |
| WSA Installed | Windows Subsystem for Android must be functional |
| Developer Mode | Enabled in WSA Settings → Developer |
| ADB Debugging | Enabled in WSA Settings → Developer |
| Administrator | Run terminal as administrator |
| Python 3.10+ | Only when running from source (`python twrp.py …`) |
| PySide6 6.5+ | Only for the IMG Manager (`twrp.py --gui`) |

### Bundled tools

Running from the repository (or a release zip that ships `assets/`) needs **no
extra downloads** — the tool picks these up automatically:

| Asset | Used for |
|:------|:---------|
| `assets/7z.exe` | extracting `twrp.7z` / `fix.7z` |
| `assets/adb.exe` (+ `cygwin1.dll`) | ADB when it is not on `PATH` |
| `assets/aaptpp.exe` | reading APK package names (`--install-as-system-app`) |
| `assets/img-checker.exe`, `assets/img-creater.exe` | unpacking / repacking nested `.img` files |
| `assets/icon.ico`, `assets/twrp.ico` | `.img` *Open with* icon (`--register-img`) |
| `assets/fix.7z` | Magisk hook payload (`--install-magisk-hook`) |

### Install ADB (if not installed)

1. Download [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)
2. Extract to a folder (e.g., `C:\platform-tools`)
3. Add to system PATH or use full path

Verify ADB is working:

```cmd
adb devices
```

You should see your WSA device listed:

```
List of devices attached
127.0.0.1:58526    device
```

---

## Download

Download the latest release from the [Releases page](https://github.com/WSA-Installer/twrp-for-wsa/releases/latest):

| File | Description |
|:-----|:------------|
| `twrp.exe` | The injector tool |
| `twrp.7z` | TWRP ramdisk files (may be bundled with twrp.exe) |

Place both files in the same directory.

---

## Inject TWRP

Open a terminal as **administrator** and navigate to the directory containing `twrp.exe`:

```cmd
cd C:\path\to\twrp
```

Run the inject command:

```cmd
twrp.exe --inject twrp.7z
```

### What This Does

1. Extracts `twrp.7z` to a temporary directory
2. Reads `patch.json` to understand file mapping
3. Locates WSA's `initrd.img` in the WSA installation directory
4. Creates a backup `initrd.img.bak` next to the original
5. Injects TWRP files into the cpio archive:
   - `/init` — Custom dispatcher ELF binary
   - `/info.json` — Metadata with recovery flag
   - `/sbin/twrp` — Main TWRP binary
   - `/sbin/busybox` — Shell utilities
   - `/twres/` — Theme and resources
   - `/system/lib64/` — Required libraries
6. Writes the patched `initrd.img` back

### Inject into Specific Path

If WSA is installed in a non-standard location:

```cmd
twrp.exe --inject twrp.7z --path D:\WSA\initrd.img
```

### Inject Individual Files

To inject a single file:

```cmd
twrp.exe --inject-file info.json
twrp.exe --inject-file info.json into /config/
```

To inject a folder:

```cmd
twrp.exe --inject-folder twrp_files/
twrp.exe --inject-folder twrp_files/ into /overlay.d/
```

---

## Enable TWRP Mode

After injection, enable TWRP boot mode:

```cmd
twrp.exe --enable-twrp
```

This sets `recovery_flag` to `"true"` inside `/info.json` in the initrd.img.

### Restart WSA

For the change to take effect, restart WSA:

1. Open **Windows Settings** → **Apps** → **Installed Apps**
2. Find **Windows Subsystem for Android**
3. Click **Terminate** (if running)
4. Or run via ADB:

```cmd
adb reboot recovery
```

TWRP will boot instead of Android.

---

## Verify Installation

### Check Status

```cmd
twrp.exe --status
```

Expected output:

```
=== TWRP for WSA Status ===
WSA Version:       2404.40000.2.0
Recovery Flag:     true
TWRP Support:      true
Amazon Support:    false
Note:              TWRP Recovery enabled
--- Module images ---
admin:  lsp_wsa-installer.img       present
user:   lsp_wsa-installer-user.img  present
```

### Check ADB

With TWRP running, verify ADB connection:

```cmd
adb devices
```

Expected output:

```
List of devices attached
127.0.0.1:58526    recovery
```

The `recovery` status confirms TWRP is active.

---

## System Apps, Modules & Hook

Optional steps — every one of them defaults to the **USER** module image, so
you can skip them entirely.

### Install an APK as a system app

```cmd
twrp.exe --install-as-system-app app.apk            (USER module — no password)
twrp.exe --install-as-system-app app.apk --admin    (ADMIN module — asks for the password)
twrp.exe --update-as-system-app app.apk             (overwrite an existing system app)
```

The APK's package name is read with `assets/aaptpp.exe`, the old entry is
replaced inside `lsp_wsa-installer[-user].img`, and a `*.img.bak-*` is written
first. Details: [Admin & User Modules](admin-user-modules.md).

After writing the image the flow starts WSA, waits for
`sys.boot_completed=1` and runs `pm list packages` for every APK
(`ADBManager.verify_boot_and_packages()`). The log then shows either

```
Verified: com.example.app is installed and visible
```

or, when the package is not visible yet (the module is merged at the *next*
post-fs-data — the usual case on the very first boot):

```
NOT visible yet: com.example.app
  The module is merged at the next post-fs-data - reboot WSA once more and re-check.
  Boot diagnostics: adb root; cat /data/adb/lsp-boot.log
```

Boot logs themselves: `/data/adb/lsp-boot.log` (persistent, needs `adb root`)
and `/storage/emulated/0/WSA Installer/post-fs-data.log` (plain file, copied
after every boot). Details: [Magisk Hook — Boot logging](magisk-hook.md#boot-logging).

### See what is pre-installed

```cmd
twrp.exe --list-of-boltware
```

Scans **both** module images and prints a de-duplicated list tagged `admin`
or `user`.

### Remove a system app on next boot

```cmd
twrp.exe --uninstall-boltware com.example.app
```

Adds the package to `uninstall.txt`; the boot hook applies it the next time
Android starts. Details: [Boltware Manager](boltware-manager.md).

### Install the boot hook

```cmd
twrp.exe --install-magisk-hook     # first-time install
twrp.exe --repaire-magisk-hook     # force rebuild from assets/fix.7z
```

Audits come from `hook_issues()` — an empty result means the hook is healthy.
Details: [Magisk Hook](magisk-hook.md).

---

## IMG Manager & .img Open With

### Open the archive editor

```cmd
twrp.exe --gui
```

Browse `initrd.img` like a 7-Zip archive: extract, open nested
cpio/tar/zip/7z/gz/xz/bz2 archives, edit scripts in place, stage changes and
repack. Every save creates an `*.img.bak-YYYYMMDD-HHMMSS` backup with a
restore picker. Details: [IMG Manager](img-manager.md).

### Double-click `.img` files in Explorer

```cmd
twrp.exe --register-img      # .img -> Open with -> WSA IMG Manager
twrp.exe --unregister-img    # remove the association (idempotent)
```

Written to HKLM when elevated, HKCU otherwise. Details:
[Open With Registry](open-with-registry.md).

---

## Reboot Back to Android

To return to normal Android boot:

```cmd
twrp.exe --disable-twrp
```

Then restart WSA:

```cmd
adb reboot
```

Or terminate WSA from Windows Settings and relaunch it.

---

## Restore Original initrd.img

To disable TWRP and revert to normal Android boot:

```cmd
twrp.exe --disable-twrp
```

Then restart WSA. The dispatcher will read `recovery_flag: "false"` and boot Android normally.

> **Note:** TWRP for WSA does not create a separate backup file. The `--disable-twrp` command modifies the `recovery_flag` in `info.json` within the existing initrd.img. If you need to completely remove TWRP, re-inject a clean initrd.img from your WSA installation.

---

## What's Next?

- [CLI Commands Reference](commands.md) — Full list of all twrp.exe commands
- [CLI Reference](cli-reference.md) — Every option, exit code and example
- [Architecture](architecture.md) — How TWRP for WSA works internally
- [Troubleshooting](troubleshooting.md) — Common issues and solutions
- [Admin & User Modules](admin-user-modules.md) — Dual module images + password gate
- [IMG Manager](img-manager.md) — `--gui` archive browser, Edit/Pack, backups
- [Open With Registry](open-with-registry.md) — `.img` right-click integration
- [Magisk Hook](magisk-hook.md) — Boot hook install / repair / audit
- [Boltware Manager](boltware-manager.md) — List and remove system apps
- [Boot Dispatcher](dispatcher.md) — `init.c` build and verification
