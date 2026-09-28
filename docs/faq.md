# Frequently Asked Questions

Common questions about TWRP for WSA.

---

## Table of Contents

- [General](#general)
- [Installation](#installation)
- [Usage](#usage)
- [Modules, IMG Manager & Hook](#modules-img-manager--hook)
- [Troubleshooting](#troubleshooting)
- [Compatibility](#compatibility)

---

## General

### What is TWRP for WSA?

TWRP for WSA brings full Team Win Recovery Project functionality to Windows Subsystem for Android. It works by injecting TWRP's ramdisk files directly into WSA's `initrd.img` and installing a custom dispatcher that decides at boot time whether to load TWRP or Android.

### Is TWRP for WSA free?

Yes. TWRP for WSA is open-source under the Source-Available / Community-Extension License.

### Do I need root?

No. TWRP for WSA works on both rooted and non-rooted WSA installations. However, some TWRP features (like NANDroid backup) work best with root access.

### Will this void my warranty?

No. TWRP for WSA modifies only WSA's `initrd.img` and does not affect the host Windows system. The modification is reversible by disabling TWRP mode.

---

## Installation

### How do I install TWRP for WSA?

1. Download `twrp.exe` and `twrp.7z` from the [latest release](https://github.com/WSA-Installer/twrp-for-wsa/releases/latest)
2. Open a terminal as administrator
3. Run: `twrp.exe --inject twrp.7z`
4. Enable TWRP: `twrp.exe --enable-twrp`
5. Restart WSA

See the [Installation Guide](installation.md) for detailed instructions.

### What are the system requirements?

- Windows 10 (build 19041+) or Windows 11
- WSA installed and functional
- 50 MB free disk space
- Administrator privileges

See [System Requirements](installation.md#prerequisites) for details.

### Can I install TWRP on ARM64?

Yes. WSA runs an x86_64 Linux kernel on all platforms, including ARM64 via binary translation. The TWRP binary is compiled for x86_64, which works on all platforms.

---

## Usage

### How do I enter TWRP recovery?

```cmd
twrp.exe --enable-twrp
adb reboot recovery
```

### How do I exit TWRP recovery?

```cmd
twrp.exe --disable-twrp
adb reboot
```

### How do I backup WSA?

With TWRP running:

```cmd
adb shell twrp backup
```

### How do I restore a backup?

With TWRP running:

```cmd
adb shell twrp restore
```

### Can I flash Magisk with TWRP?

Yes. Copy the Magisk ZIP to WSA and flash it via TWRP:

```cmd
adb push magisk.zip /sdcard/
adb shell twrp install /sdcard/magisk.zip
```

---

## Modules, IMG Manager & Hook

### What is the difference between ADMIN and USER?

System apps and hook files live in **two module images**, injected next to
the main initrd:

| Mode | Image | Used by |
|:-----|:------|:--------|
| ADMIN | `lsp_wsa-installer.img` | `--admin`, `--install-as-system-app … --admin` |
| USER | `lsp_wsa-installer-user.img` | default when no flag is given |

The USER image is always safe to touch; ADMIN is protected. See
[Admin & User Modules](admin-user-modules.md).

### Why does `--admin` ask for a password?

The gate runs **before any archive is opened**, so a failed password never
leaves a partially-written image behind. It compares the SHA-256 of your
input, allows 3 attempts, and can be automated with
`WSA_ADMIN_PASSWORD`. See [admin-user-modules.md](admin-user-modules.md#password-gate).

### How do I list the pre-installed system apps?

```cmd
twrp.exe --list-of-boltware
```

Both images are scanned and each package is tagged `admin` or `user`
(de-duplicated union).

### How do I remove a system app permanently?

```cmd
twrp.exe --uninstall-boltware com.example.app
```

The package is added to `uninstall.txt`; the boot hook applies the removal
on the **next** boot of Android. Details:
[boltware-manager.md](boltware-manager.md).

### How do I install an APK as a system app?

```cmd
twrp.exe --install-as-system-app app.apk            (USER module)
twrp.exe --install-as-system-app app.apk --admin    (ADMIN module)
twrp.exe --update-as-system-app app.apk
```

### What does `--gui` do?

Opens the **IMG Manager** — a 7-Zip-style browser for `initrd.img`: extract,
open inner archives (cpio/tar/zip/7z/gz/xz/bz2), edit scripts in place,
stage changes and repack. Every save creates an
`*.img.bak-YYYYMMDD-HHMMSS` backup first, with a restore picker.
[img-manager.md](img-manager.md).

### How do I open `.img` files by double-click in Explorer?

```cmd
twrp.exe --register-img
```

Registers `.img` → *Open with* → **WSA IMG Manager** (HKLM, HKCU fallback).
Undo with `--unregister-img` — it is idempotent.
[open-with-registry.md](open-with-registry.md).

### What is the Magisk hook?

A set of files under `overlay.d/sbin` (plus a marked block in
`post-fs-data.sh`) that runs early in the Android boot and applies scheduled
changes such as `uninstall.txt`.

```cmd
twrp.exe --install-magisk-hook     # install
twrp.exe --repaire-magisk-hook     # force rebuild from fix.7z
```

`hook_issues()` audits the result.
[magisk-hook.md](magisk-hook.md).

### Where is the compiled dispatcher?

`prebuilt/init` (static ELF64, musl-gcc) with its checksum in
`prebuilt/SHA256SUMS`. It is rebuilt by the `build-dispatcher.yml` workflow.
[dispatcher.md](dispatcher.md).

---

## Troubleshooting

### TWRP is not booting

1. Check status: `twrp.exe --status`
2. Ensure `recovery_flag` shows `true`
3. If not enabled, run: `twrp.exe --enable-twrp`
4. Restart WSA completely

### ADB shows "device" instead of "recovery"

1. TWRP has not booted yet
2. Verify the flag is set: `twrp.exe --status`
3. Restart WSA after enabling TWRP
4. TWRP recovery auto-starts on next boot

### ADB not connecting

1. Restart ADB: `adb kill-server && adb start-server`
2. Connect manually: `adb connect 127.0.0.1:58526`
3. Enable Developer Mode and ADB Debugging in WSA Settings only if you need ADB access to Android (not required for TWRP recovery)

### Flag reverts after WSA update

WSA updates replace the `initrd.img`. After an update, re-inject TWRP:

```cmd
twrp.exe --inject twrp.7z
twrp.exe --enable-twrp
```

---

## Compatibility

### Which WSA versions are supported?

TWRP for WSA supports all WSA image variants with x86_64 architecture. See [Supported Images](supported-images.md) for the complete list.

### Does this work with Play Store?

Yes. TWRP for WSA is compatible with WSA installations that include Google Play Store.

### Does this work with Magisk?

Yes. TWRP for WSA is compatible with Magisk-rooted WSA images.

### Does this work with Amazon Appstore?

Yes. TWRP for WSA supports WSA images with and without Amazon Appstore.

---

## Related Documentation

- [Installation Guide](installation.md) — Step-by-step installation
- [CLI Commands](commands.md) — Full command reference
- [Architecture](architecture.md) — How it works internally
- [Supported Images](supported-images.md) — All 7 WSA variants
- [Troubleshooting](troubleshooting.md) — Common issues and solutions
- [Admin & User Modules](admin-user-modules.md) — Dual module images + password gate
- [IMG Manager](img-manager.md) — `--gui` archive browser and Edit/Pack
- [Open With Registry](open-with-registry.md) — `.img` right-click integration
- [Magisk Hook](magisk-hook.md) — Boot hook install, repair, audit
- [Boltware Manager](boltware-manager.md) — List and remove system apps
- [Boot Dispatcher](dispatcher.md) — `init.c` build and verification
