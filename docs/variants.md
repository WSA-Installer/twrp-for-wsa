# WSA Image Variants

Documentation for all 7 custom WSA 2407.40000.4.0 image variants with TWRP Recovery support.

---

## Table of Contents

- [Overview](#overview)
- [Variant 1 — GApps Standard](#variant-1--gapps-standard)
- [Variant 2 — GApps + NoAmazon](#variant-2--gapps--noamazon)
- [Variant 3 — Magisk Stable + GApps](#variant-3--magisk-stable--gapps)
- [Variant 4 — NoGApps](#variant-4--nogapps)
- [Variant 5 — Magisk Canary + GApps + NoAmazon](#variant-5--magisk-canary--gapps--noamazon)
- [Variant 6 — Magisk Stable + NoGApps + NoAmazon](#variant-6--magisk-stable--nogapps--noamazon)
- [Variant 7 — NoGApps + NoAmazon](#variant-7--nogapps--noamazon)
- [Injection Order](#injection-order)

---

## Overview

All variants are built from WSA **2407.40000.4.0** x64 Release-Nightly images and include TWRP Recovery support. Each variant has a different combination of Google Apps, Magisk root, and Amazon Appstore support.

### How to Use

1. Choose the variant that matches your needs
2. Copy the `info.json` content for that variant
3. Save it as `info.json` in your working directory
4. Run the inject command with the variant's image path
5. Verify with the status command

---

## Variant 1 — GApps Standard

**Description:** Standard WSA with Google Apps and Amazon Appstore.

**Features:**
- Google Apps included
- Amazon Appstore included
- Non-root configuration
- Standard Amazon configuration

**Recommended for:** Users who want Google-related Android functionality without Magisk root.

### info.json

```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "True",
  "build_version": "4.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "TWRP Recovery enabled for WSA 2407.40000.4.0 x64 GApps Standard variant."
}
```

### Commands

```cmd
:: Inject info.json
twrp.exe --inject-file info.json --path <initrd_path>

:: Verify
twrp.exe --status --path <initrd_path>
```

---

## Variant 2 — GApps + NoAmazon

**Description:** WSA with Google Apps, without Amazon Appstore.

**Features:**
- Google Apps included
- Amazon Appstore excluded
- Non-root configuration
- Google-oriented configuration

**Recommended for:** Users who want Google Apps but do not want Amazon Appstore.

### info.json

```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "False",
  "build_version": "4.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "TWRP Recovery enabled for WSA 2407.40000.4.0 x64 GApps + NoAmazon variant."
}
```

### Commands

```cmd
twrp.exe --inject-file info.json --path <initrd_path>
twrp.exe --status --path <initrd_path>
```

---

## Variant 3 — Magisk Stable + GApps

**Description:** WSA with Google Apps, Magisk stable root, and Amazon Appstore.

**Features:**
- Google Apps included
- Magisk 30.6.30600 stable root included
- Amazon Appstore included
- Root-enabled configuration

**Recommended for:** Advanced users who need root with Google Apps.

### info.json

```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "True",
  "root_method": "Magisk",
  "amazon_support": "True",
  "build_version": "4.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "TWRP Recovery enabled for WSA 2407.40000.4.0 x64 Magisk Stable + GApps variant."
}
```

### Commands

```cmd
twrp.exe --inject-file info.json --path <initrd_path>
twrp.exe --status --path <initrd_path>
```

---

## Variant 4 — NoGApps

**Description:** WSA without Google Apps, with Amazon Appstore.

**Features:**
- Google Apps excluded
- Amazon Appstore included
- Non-root configuration
- Minimal configuration

**Recommended for:** Users who do not need Google Apps and prefer a clean environment.

### info.json

```json
{
  "twrp_support": "True",
  "gapp_support": "False",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "True",
  "build_version": "4.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "TWRP Recovery enabled for WSA 2407.40000.4.0 x64 NoGApps variant."
}
```

### Commands

```cmd
twrp.exe --inject-file info.json --path <initrd_path>
twrp.exe --status --path <initrd_path>
```

---

## Variant 5 — Magisk Canary + GApps + NoAmazon

**Description:** WSA with Google Apps, Magisk canary root, without Amazon Appstore.

**Features:**
- Google Apps included
- Magisk 30.6.30600 canary root included
- Amazon Appstore excluded
- Bleeding-edge Magisk

**Recommended for:** Advanced users who want the latest Magisk features without Amazon.

### info.json

```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "True",
  "root_method": "Magisk Canary",
  "amazon_support": "False",
  "build_version": "4.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "TWRP Recovery enabled for WSA 2407.40000.4.0 x64 Magisk Canary + GApps + NoAmazon variant."
}
```

### Commands

```cmd
twrp.exe --inject-file info.json --path <initrd_path>
twrp.exe --status --path <initrd_path>
```

---

## Variant 6 — Magisk Stable + NoGApps + NoAmazon

**Description:** WSA with Magisk stable root, without Google Apps and Amazon Appstore.

**Features:**
- Google Apps excluded
- Magisk 30.6.30600 stable root included
- Amazon Appstore excluded
- Minimal root-only configuration

**Recommended for:** Advanced users who need root without Google or Amazon components.

### info.json

```json
{
  "twrp_support": "True",
  "gapp_support": "False",
  "root_support": "True",
  "root_method": "Magisk",
  "amazon_support": "False",
  "build_version": "4.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "TWRP Recovery enabled for WSA 2407.40000.4.0 x64 Magisk Stable + NoGApps + NoAmazon variant."
}
```

### Commands

```cmd
twrp.exe --inject-file info.json --path <initrd_path>
twrp.exe --status --path <initrd_path>
```

---

## Variant 7 — NoGApps + NoAmazon

**Description:** Minimal WSA without Google Apps and Amazon Appstore.

**Features:**
- Google Apps excluded
- Amazon Appstore excluded
- Non-root configuration
- Minimal base

**Recommended for:** Users who want the cleanest WSA environment.

### info.json

```json
{
  "twrp_support": "True",
  "gapp_support": "False",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "False",
  "build_version": "4.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "TWRP Recovery enabled for WSA 2407.40000.4.0 x64 NoGApps + NoAmazon variant."
}
```

### Commands

```cmd
twrp.exe --inject-file info.json --path <initrd_path>
twrp.exe --status --path <initrd_path>
```

---

## Injection Order

To inject all 7 variants:

```cmd
:: Step 1: Save each variant's info.json to your working directory
:: Step 2: Run inject for each variant

:: --- Variant 1: GApps Standard ---
twrp.exe --inject-file info.json --path <path_to_variant1_initrd>

:: --- Variant 2: GApps + NoAmazon ---
twrp.exe --inject-file info.json --path <path_to_variant2_initrd>

:: --- Variant 3: Magisk Stable + GApps ---
twrp.exe --inject-file info.json --path <path_to_variant3_initrd>

:: --- Variant 4: NoGApps ---
twrp.exe --inject-file info.json --path <path_to_variant4_initrd>

:: --- Variant 5: Magisk Canary + GApps + NoAmazon ---
twrp.exe --inject-file info.json --path <path_to_variant5_initrd>

:: --- Variant 6: Magisk Stable + NoGApps + NoAmazon ---
twrp.exe --inject-file info.json --path <path_to_variant6_initrd>

:: --- Variant 7: NoGApps + NoAmazon ---
twrp.exe --inject-file info.json --path <path_to_variant7_initrd>

:: Step 3: Verify each variant
twrp.exe --status --path <path_to_variant_initrd>
```

---

## Variant Comparison

| Variant | GApps | Root | Amazon | Use Case |
|:--------|:------|:-----|:-------|:---------|
| 1 — GApps Standard | Yes | No | Yes | Standard Google functionality |
| 2 — GApps + NoAmazon | Yes | No | No | Google without Amazon |
| 3 — Magisk Stable + GApps | Yes | Yes | Yes | Rooted with Google |
| 4 — NoGApps | No | No | Yes | Clean without Google |
| 5 — Magisk Canary + GApps + NoAmazon | Yes | Yes | No | Bleeding-edge root |
| 6 — Magisk Stable + NoGApps + NoAmazon | No | Yes | No | Minimal root |
| 7 — NoGApps + NoAmazon | No | No | No | Cleanest configuration |

---

## TWRP Recovery in All Variants

All variants include TWRP Recovery with the same capabilities:

- Full system backup and restore (NANDroid backup)
- Flash custom ZIP files and modifications
- File manager for browsing and editing system files
- ADB sideload for installing packages
- Terminal access for advanced operations
- Partition management and formatting

### How It Works in WSA

The WSA boot chain starts with the Linux kernel loading `/init`, which is a custom dispatcher ELF. On boot, the dispatcher reads `/info.json` and checks the `recovery_flag` field. If `recovery_flag` is set to `"true"` (case-insensitive), the dispatcher boots into TWRP by executing `/sbin/twrp` instead of the normal Android init. If `recovery_flag` is `"false"`, it proceeds with the standard WSA boot through `lspinit` and `wsainit` into Android.

**To enter TWRP:** set `recovery_flag` to `"true"` and reboot WSA.
**To exit TWRP:** set `recovery_flag` to `"false"` and reboot WSA.
