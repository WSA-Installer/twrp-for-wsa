# Installation Guide

Step-by-step instructions for installing TWRP recovery into WSA.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Download](#download)
- [Inject TWRP](#inject-twrp)
- [Enable TWRP Mode](#enable-twrp-mode)
- [Verify Installation](#verify-installation)
- [Reboot Back to Android](#reboot-back-to-android)
- [Restore Original initrd.img](#restore-original-initrdimg)

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
4. Copies the original `initrd.img` as backup
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

The injector creates a backup of the original `initrd.img` during injection. To restore:

```cmd
twrp.exe --disable-twrp
twrp.exe --status
```

If you need to manually restore the backup, look for the `.bak` file in the WSA installation directory and rename it back to `initrd.img`.

---

## What's Next?

- [CLI Commands Reference](commands.md) — Full list of all twrp.exe commands
- [Architecture](architecture.md) — How TWRP for WSA works internally
- [Troubleshooting](troubleshooting.md) — Common issues and solutions
