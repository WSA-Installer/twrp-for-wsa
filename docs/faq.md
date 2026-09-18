# Frequently Asked Questions

Common questions about TWRP for WSA.

---

## Table of Contents

- [General](#general)
- [Installation](#installation)
- [Usage](#usage)
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
