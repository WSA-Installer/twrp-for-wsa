# CLI Commands Reference

Complete reference for all `twrp.exe` commands and options.

---

## Table of Contents

- [Overview](#overview)
- [Commands](#commands)
  - [--status](#--status)
  - [--inject](#--inject)
  - [--inject-file](#--inject-file)
  - [--inject-folder](#--inject-folder)
  - [--enable-twrp](#--enable-twrp)
  - [--disable-twrp](#--disable-twrp)
  - [--install-twrp](#--install-twrp)
  - [--repair-twrp](#--repair-twrp)
  - [--uninstall-twrp](#--uninstall-twrp)
  - [--path](#--path)
  - [--debug](#--debug)
  - [--gui](#--gui)
  - [--install-as-system-app](#--install-as-system-app)
  - [--update-as-system-app](#--update-as-system-app)
  - [--admin / --user](#--admin--user)
  - [--list-of-boltware](#--list-of-boltware)
  - [--uninstall-boltware](#--uninstall-boltware)
  - [--install-magisk-hook](#--install-magisk-hook)
  - [--repaire-magisk-hook](#--repaire-magisk-hook)
  - [--uninstall-magisk-hook](#--uninstall-magisk-hook)
  - [--register-img / --unregister-img](#--register-img--unregister-img)
- [The `into` Keyword](#the-into-keyword)
- [Exit Codes](#exit-codes)
- [Examples](#examples)

---

## Overview

`twrp.exe` is a command-line tool for managing TWRP recovery in Windows Subsystem for Android. All commands operate on WSA's `initrd.img` file.

### Basic Syntax

```cmd
twrp.exe [OPTIONS]
```

### Finding Your WSA initrd.img

The tool automatically locates WSA's initrd.img in the standard installation path:

```
%LOCALAPPDATA%\Packages\MicrosoftCorporationII.WindowsSubsystemForAndroid_8wekyb3d8bbwe\LocalState\initrd.img
```

Use `--path` to specify a custom location.

---

## Commands

### --status

Check the current state of WSA and TWRP.

```cmd
twrp.exe --status
```

**Output:**

```
=== TWRP for WSA Status ===
WSA Version:       2404.40000.2.0
Recovery Flag:     true
TWRP Support:      true
Amazon Support:    false
Note:              TWRP Recovery enabled
```

**Fields:**

| Field | Description |
|:------|:------------|
| WSA Version | Detected WSA version from initrd.img |
| Recovery Flag | Current boot mode (`true` = TWRP, `false` = Android) |
| TWRP Support | Whether TWRP files are present in initrd.img |
| Amazon Support | Whether Amazon Appstore is supported |
| Note | Human-readable description (shown when non-empty) |

**With custom path:**

```cmd
twrp.exe --status --path D:\initrd.img
```

---

### --inject

Extract a `.7z` archive and inject TWRP files into WSA's initrd.img. This is the primary command for installing TWRP.

```cmd
twrp.exe --inject twrp.7z
```

**What it does:**

1. Extracts `twrp.7z` to a temporary directory (`%TEMP%\twrp_temp\`)
2. Reads `patch.json` from the extracted files
3. Locates WSA's `initrd.img`
4. Creates a backup (`.bak` file)
5. Patches files into the cpio archive based on `patch.json` mapping
6. Writes the patched initrd.img back

**Syntax:**

```cmd
twrp.exe --inject <archive.7z>
twrp.exe --inject <archive.7z> into <destination>
twrp.exe --inject <archive.7z> --path <initrd.img>
```

**The `into` keyword** specifies a custom destination prefix within the cpio archive. By default, files are injected at `/`.

```cmd
twrp.exe --inject twrp.7z into /overlay.d/
```

**With custom initrd path:**

```cmd
twrp.exe --inject twrp.7z --path D:\initrd.img
```

---

### --inject-file

Inject a single file into WSA's initrd.img.

```cmd
twrp.exe --inject-file info.json
```

**Syntax:**

```cmd
twrp.exe --inject-file <file>
twrp.exe --inject-file <file> into <destination>
twrp.exe --inject-file <file> --path <initrd.img>
```

**Examples:**

```cmd
:: Inject info.json to root of initrd.img
twrp.exe --inject-file info.json

:: Inject into a subfolder
twrp.exe --inject-file info.json into /config/

:: Inject into specific initrd.img
twrp.exe --inject-file info.json into / --path D:\initrd.img
```

**How it resolves paths:**

| Source | Result |
|:-------|:-------|
| `info.json` | Parsed as `pick=info.json`, `drop=/` |
| `info.json into /config/` | Parsed as `pick=info.json`, `drop=/config/` |

---

### --inject-folder

Inject the contents of a folder into WSA's initrd.img.

```cmd
twrp.exe --inject-folder twrp_files/
```

**Syntax:**

```cmd
twrp.exe --inject-folder <folder>
twrp.exe --inject-folder <folder> into <destination>
twrp.exe --inject-folder <folder> --path <initrd.img>
```

**Examples:**

```cmd
:: Inject folder contents to root
twrp.exe --inject-folder twrp_files/

:: Inject into specific location
twrp.exe --inject-folder twrp_files/ into /sbin/

:: Inject into specific initrd.img
twrp.exe --inject-folder twrp_files/ into /sbin/ --path D:\initrd.img
```

**How it works:**

1. Scans the source folder recursively
2. For each file, resolves the destination within the cpio archive
3. Creates new cpio entries or replaces existing ones
4. Writes the modified archive back

---

### --enable-twrp

Set the recovery flag to `true` in info.json. On next boot, WSA will load TWRP instead of Android.

```cmd
twrp.exe --enable-twrp
```

**What it does:**

1. Reads the current info.json from initrd.img
2. Sets `recovery_flag` to `"true"`
3. Writes the modified info.json back

**Installed-check gate:** refuses to flip the flag (and leaves it untouched)
when `twrp_support` is `false` (points at `--install-twrp`) or
`twrp_missing()` is non-empty (lists what is missing, points at
`--repair-twrp`).

**Syntax:**

```cmd
twrp.exe --enable-twrp
twrp.exe --enable-twrp --path <initrd.img>
```

**After enabling:**

```cmd
:: Reboot WSA into recovery
adb reboot recovery
```

---

### --disable-twrp

Clear the recovery flag (set to `false`). On next boot, WSA will load Android normally.

```cmd
twrp.exe --disable-twrp
```

**What it does:**

1. Reads the current info.json from initrd.img
2. Sets `recovery_flag` to `"false"`
3. Writes the modified info.json back

**Syntax:**

```cmd
twrp.exe --disable-twrp
twrp.exe --disable-twrp --path <initrd.img>
```

**After disabling:**

```cmd
:: Reboot WSA into Android
adb reboot
```

---

### --install-twrp

```cmd
twrp.exe --install-twrp [--path <initrd.img>]
```

Injects `assets/twrp.7z` (via its `patch.json` map) and sets
`twrp_support = "true"`, then reports whatever `twrp_missing()` still finds.
Skips with `TWRP already installed, nothing to do` when the flag is set and
nothing is missing. A placeholder payload logs `Payload skipped: …` while the
flag is still flipped — fill `assets/twrp.7z` and run `--repair-twrp`.

---

### --repair-twrp

```cmd
twrp.exe --repair-twrp [--path <initrd.img>]
```

Force re-injection of the TWRP payload (`force=True`, same idea as
`--repaire-magisk-hook`): the "already installed" short circuit is skipped,
`twrp_support` is re-asserted `true` and the result is verified with
`twrp_missing()`. Use it after `--enable-twrp` reports
`TWRP install is incomplete`.

---

### --uninstall-twrp

```cmd
twrp.exe --uninstall-twrp [--path <initrd.img>]
```

Removes `/sbin/twrp`, `/sbin/busybox`, `/sbin/linker64` and the trees
`/twres/`, `/etc/`, `/system/lib64/`; swaps a regular `/init` dispatcher back
to the symlink `init -> lspinit` (when `lspinit` exists); sets
`twrp_support = "false"` and `recovery_flag = "false"` (both transitions
logged, ends with `TWRP uninstalled`). No-op with
`TWRP is not installed - nothing to remove`. The Magisk hook is not touched.

---

### --path

Specify a custom path to `initrd.img`. Use this when WSA is installed in a non-standard location.

```cmd
twrp.exe --status --path D:\custom\initrd.img
```

**Works with all commands:**

```cmd
twrp.exe --inject twrp.7z --path D:\initrd.img
twrp.exe --inject-file info.json --path D:\initrd.img
twrp.exe --inject-folder twrp_files/ --path D:\initrd.img
twrp.exe --enable-twrp --path D:\initrd.img
twrp.exe --disable-twrp --path D:\initrd.img
```

---

### --debug

Enable verbose debug output for troubleshooting.

```cmd
twrp.exe --inject twrp.7z --debug
```

**Output includes:**

- Detailed path resolution
- Cpio entry names and sizes
- Flag replacement bytes
- Temporary file locations

---

### --gui

Open the **IMG Manager** for browsing and editing the cpio archive.

```cmd
twrp.exe --gui
twrp.exe --gui --path D:\initrd.img
```

Resolves the image from `--path` → `<WSA>\Tools\initrd.img` → file dialog, and
offers a `*.img.bak-*` backup if the live image cannot be read.
Full guide: [IMG Manager](img-manager.md).

---

### --install-as-system-app

```cmd
twrp.exe --install-as-system-app <APK…> [--admin | --user] [--path <initrd.img>]
```

Installs APK(s) into the module image. **Defaults to the USER module**; pass
`--admin` to target the ADMIN module (password prompt).

---

### --update-as-system-app

```cmd
twrp.exe --update-as-system-app <APK…> [--admin | --user]
```

Same as install, but overwrites an app that is already present
(`force_update=True`).

---

### --admin / --user

```cmd
twrp.exe --install-as-system-app app.apk --admin    # lsp_wsa-installer.img (password)
twrp.exe --list-of-boltware --user                  # lsp_wsa-installer-user.img
```

Mutually exclusive (`--admin --user` → exit 2). Defaults:
install/update = `--user`; `--list-of-boltware` / `--uninstall-boltware` with no
flag scan **both**; `--status` always reports both.
Full guide: [Admin & User Modules](admin-user-modules.md).

---

### --list-of-boltware

```cmd
twrp.exe --list-of-boltware [--admin | --user] [--path <initrd.img>]
```

Lists system apps per module image (`[admin]` / `[user]` sections). Requires a
non-stock image.

---

### --uninstall-boltware

```cmd
twrp.exe --uninstall-boltware [PACKAGE…] [--admin | --user]
```

No package argument = remove the whole module image. Packages are merged and
de-duplicated across the selected images, written to `overlay.d/sbin/uninstall.txt`
once, and removed **on the next boot**.
Full guide: [Boltware Manager](boltware-manager.md).

---

### --install-magisk-hook

```cmd
twrp.exe --install-magisk-hook [--path <initrd.img>]
```

Installs the boot hook (`overlay.d/sbin/post-fs-data.sh` + `lspinit` /
`magiskinit` / `wsainit`) from `assets/fix.7z`. Skips when already present.

---

### --repaire-magisk-hook

```cmd
twrp.exe --repaire-magisk-hook [--path <initrd.img>]    # alias: --repair-magisk-hook
```

Force a full rebuild from `fix.7z`, discarding the installed hook, then verify
with `hook_issues()`. Full guide: [Magisk Hook](magisk-hook.md).

---

### --uninstall-magisk-hook

```cmd
twrp.exe --uninstall-magisk-hook [--path <initrd.img>]
```

Restores the stock boot chain: renames the saved WSA init back
(`wsainit -> init`, aborting if it is missing while `/init` is a symlink),
deletes the hook payload (`lspinit`, `magiskinit`, `post-fs-data.sh`,
`init-ld.xz`, `magisk.xz`, `stub.xz`, `uninstall.txt`, `.backup/`) and
removes the whole `overlay.d/` tree — module images included. Ends with
`Magisk hook uninstalled (N entries removed)`; the TWRP flags are left
untouched. Full guide: [Magisk Hook](magisk-hook.md).

---

### --register-img / --unregister-img

```cmd
twrp.exe --register-img        # .img -> Open with -> WSA IMG Manager
twrp.exe --unregister-img      # remove those keys again
```

Writes additive Explorer keys under `HKLM\Software\Classes` (falls back to
`HKCU`) and never changes `.img`'s default handler. Also runs automatically on
app start. Full guide: [Open With Registry](open-with-registry.md).

---

## The `into` Keyword

The `into` keyword is a **literal keyword** (not a flag) that separates the source from the destination within the cpio archive.

### Syntax

```cmd
twrp.exe --inject <source> into <destination>
```

### Rules

- `into` must be a standalone word (not part of a path)
- The destination must start with `/`
- The destination specifies a prefix within the cpio archive
- If no `into` is specified, destination defaults to `/`

### Examples

| Command | Source | Destination |
|:--------|:-------|:------------|
| `--inject twrp.7z` | `twrp.7z` | `/` |
| `--inject twrp.7z into /overlay.d/` | `twrp.7z` | `/overlay.d/` |
| `--inject-file info.json` | `info.json` | `/` |
| `--inject-file info.json into /config/` | `info.json` | `/config/` |
| `--inject-folder sbin/ into /sbin/` | `sbin/*` | `/sbin/` |

---

## Exit Codes

| Code | Meaning |
|:-----|:--------|
| 0 | Success |
| 1 | Error (file not found, invalid archive, password refused, stock image, WSA missing) |
| 2 | Usage error (e.g. `--admin --user` together, unknown option) |

---

## Examples

### Full Installation Workflow

```cmd
:: 1. Check current status
twrp.exe --status

:: 2. Inject TWRP files
twrp.exe --inject twrp.7z

:: 3. Enable TWRP mode
twrp.exe --enable-twrp

:: 4. Reboot into TWRP
adb reboot recovery

:: 5. After using TWRP, disable and reboot
twrp.exe --disable-twrp
adb reboot
```

### Custom Installation

```cmd
:: Inject into specific initrd.img
twrp.exe --inject twrp.7z --path D:\WSA\initrd.img

:: Enable TWRP on that specific image
twrp.exe --enable-twrp --path D:\WSA\initrd.img

:: Check status
twrp.exe --status --path D:\WSA\initrd.img
```

### Granular Injection

```cmd
:: Inject just the metadata
twrp.exe --inject-file info.json

:: Inject just the dispatcher
twrp.exe --inject-file init into /

:: Inject TWRP binaries
twrp.exe --inject-folder twrp_files/ into /sbin/

:: Inject theme
twrp.exe --inject-folder twres/ into /twres/
```

### Debugging

```cmd
:: Run with debug output
twrp.exe --inject twrp.7z --debug

:: Check status with debug
twrp.exe --status --debug
```

### System Apps

```cmd
:: Install into the USER module (default)
twrp.exe --install-as-system-app com.example.app.apk

:: Install into the ADMIN module (password prompt)
twrp.exe --install-as-system-app com.example.app.apk --admin

:: Overwrite an existing system app
twrp.exe --update-as-system-app com.example.app.apk --admin

:: List everything installed in both modules
twrp.exe --list-of-boltware

:: Schedule a removal for the next boot
twrp.exe --uninstall-boltware com.example.old

:: Report WSA + both modules
twrp.exe --status
```

### Hook Maintenance

```cmd
twrp.exe --install-magisk-hook
twrp.exe --repaire-magisk-hook
twrp.exe --status
```

### IMG Manager & Explorer

```cmd
twrp.exe --gui
twrp.exe --gui --path D:\initrd.img
twrp.exe --register-img
twrp.exe --unregister-img
```
