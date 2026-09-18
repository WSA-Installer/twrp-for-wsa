# Supported WSA Images

Complete list of WSA image variants supported by TWRP for WSA.

---

## Table of Contents

- [Overview](#overview)
- [Supported Variants](#supported-variants)
- [How to Check Your WSA Version](#how-to-check-your-wsa-version)
- [Image Details](#image-details)
- [Architecture Notes](#architecture-notes)

---

## Overview

TWRP for WSA supports **7 official WSA image variants** across three architectures and platforms. Each variant has a pre-built TWRP recovery image available.

All variants use the same TWRP x86_64 binary, as WSA runs on x86_64 emulation on all platforms (including ARM64 via binary translation).

---

## Supported Variants

| # | Platform | Architecture | Version | Filename |
|:--|:---------|:-------------|:--------|:---------|
| 1 | Windows x64 | x86_64 | 2404.40000.2.0 | `microsoft.windows subsystem for android_2404.40000.2.0_neutral_~_8wekyb3d8bbwe.initrd.img` |
| 2 | Windows x64 | x86_64 | 2404.40000.10.0 | `microsoft.windows subsystem for android_2404.40000.10.0_neutral_~_8wekyb3d8bbwe.initrd.img` |
| 3 | Windows x64 | x86_64 | 2404.40000.0.0 | `microsoft.windows subsystem for android_2404.40000.0.0_neutral_~_8wekyb3d8bbwe.initrd.img` |
| 4 | Windows x64 | x86_64 | 2406.40000.7.0 | `microsoft.windows subsystem for android_2406.40000.7.0_neutral_~_8wekyb3d8bbwe.initrd.img` |
| 5 | Windows ARM64 | ARM64 | 2404.40000.10.0 | `microsoft.windows subsystem for android_2404.40000.10.0_neutral_~_8wekyb3d8bbwe.initrd.img` |
| 6 | Windows ARM64 | ARM64 | 2406.40000.13.0 | `microsoft.windows subsystem for android_2406.40000.13.0_neutral_~_8wekyb3d8bbwe.initrd.img` |
| 7 | Amazon Fire | x86_64 | 2404.40000.12.0 | `microsoft.windows subsystem for android_2404.40000.12.0_neutral_~_8wekyb3d8bbwe.initrd.img` |

---

## How to Check Your WSA Version

### Method 1 — Windows Settings

1. Open **Windows Settings** → **Apps** → **Installed Apps**
2. Find **Windows Subsystem for Android**
3. Click the **three dots** → **Advanced Options**
4. Look for the **version number** under "Package version"

### Method 2 — PowerShell

```powershell
Get-AppxPackage *WindowsSubsystemForAndroid* | Select-Object Name, Version
```

### Method 3 — ADB

```cmd
adb shell getprop ro.build.display.id
```

### Method 4 — twrp.exe

```cmd
twrp.exe --status
```

Output includes:

```
WSA Version: 2404.40000.2.0
```

---

## Image Details

### Variant 1 — Windows x64 (2404.40000.2.0)

| Property | Value |
|:---------|:------|
| Platform | Windows x64 |
| Architecture | x86_64 |
| Version | 2404.40000.2.0 |
| Release Date | 2024 |
| Initrd Size | ~288 MB |
| TWRP Support | ![](https://img.shields.io/badge/Supported-3DDC84?style=flat-square) |
| Inject Command | `twrp.exe --inject twrp.7z` |

### Variant 2 — Windows x64 (2404.40000.10.0)

| Property | Value |
|:---------|:------|
| Platform | Windows x64 |
| Architecture | x86_64 |
| Version | 2404.40000.10.0 |
| Release Date | 2024 |
| Initrd Size | ~288 MB |
| TWRP Support | ![](https://img.shields.io/badge/Supported-3DDC84?style=flat-square) |
| Inject Command | `twrp.exe --inject twrp.7z` |

### Variant 3 — Windows x64 (2404.40000.0.0)

| Property | Value |
|:---------|:------|
| Platform | Windows x64 |
| Architecture | x86_64 |
| Version | 2404.40000.0.0 |
| Release Date | 2024 |
| Initrd Size | ~288 MB |
| TWRP Support | ![](https://img.shields.io/badge/Supported-3DDC84?style=flat-square) |
| Inject Command | `twrp.exe --inject twrp.7z` |

### Variant 4 — Windows x64 (2406.40000.7.0)

| Property | Value |
|:---------|:------|
| Platform | Windows x64 |
| Architecture | x86_64 |
| Version | 2406.40000.7.0 |
| Release Date | 2024 |
| Initrd Size | ~288 MB |
| TWRP Support | ![](https://img.shields.io/badge/Supported-3DDC84?style=flat-square) |
| Inject Command | `twrp.exe --inject twrp.7z` |

### Variant 5 — Windows ARM64 (2404.40000.10.0)

| Property | Value |
|:---------|:------|
| Platform | Windows ARM64 |
| Architecture | ARM64 |
| Version | 2404.40000.10.0 |
| Release Date | 2024 |
| Initrd Size | ~288 MB |
| TWRP Support | ![](https://img.shields.io/badge/Supported-3DDC84?style=flat-square) |
| Inject Command | `twrp.exe --inject twrp.7z` |

### Variant 6 — Windows ARM64 (2406.40000.13.0)

| Property | Value |
|:---------|:------|
| Platform | Windows ARM64 |
| Architecture | ARM64 |
| Version | 2406.40000.13.0 |
| Release Date | 2024 |
| Initrd Size | ~288 MB |
| TWRP Support | ![](https://img.shields.io/badge/Supported-3DDC84?style=flat-square) |
| Inject Command | `twrp.exe --inject twrp.7z` |

### Variant 7 — Amazon Fire (2404.40000.12.0)

| Property | Value |
|:---------|:------|
| Platform | Amazon Fire |
| Architecture | x86_64 |
| Version | 2404.40000.12.0 |
| Release Date | 2024 |
| Initrd Size | ~288 MB |
| TWRP Support | ![](https://img.shields.io/badge/Supported-3DDC84?style=flat-square) |
| Inject Command | `twrp.exe --inject twrp.7z` |
| Note | Amazon Appstore variant |

---

## Architecture Notes

### Why x86_64 Only?

WSA runs an x86_64 Linux kernel on all platforms:
- **Windows x64**: Native x86_64 execution
- **Windows ARM64**: x86_64 binary translation via Microsoft's emulation layer
- **Amazon Fire**: x86_64 emulation (Fire tablets use x86_64 Android)

The TWRP binary is compiled for x86_64, which works on all three platforms.

### Initrd.img Structure

All variants use the same initrd.img structure:

```
/init                    # Dispatcher ELF (replaces original lspinit)
/info.json               # Metadata with recovery_flag
/patch.json              # Injection map
/sbin/twrp               # TWRP binary
/sbin/busybox            # Multi-call shell utilities
/sbin/linker64           # Android dynamic linker
/twres/                  # TWRP theme resources
/system/lib64/           # Android shared libraries
/overlay.d/sbin/twrp     # TWRP binary location for dispatcher
```

### WSA Installation Path

Default WSA installation path:

```
%LOCALAPPDATA%\Packages\MicrosoftCorporationII.WindowsSubsystemForAndroid_8wekyb3d8bbwe\LocalState\initrd.img
```

The `twrp.exe` tool automatically detects this path. Use `--path` to override.

---

## Adding Support for New Versions

When Microsoft releases a new WSA version:

1. Obtain the new `initrd.img`
2. Verify it uses the same cpio format
3. Test injection with `twrp.exe --inject twrp.7z`
4. Verify TWRP boots with `twrp.exe --enable-twrp`
5. Update this documentation with the new variant
