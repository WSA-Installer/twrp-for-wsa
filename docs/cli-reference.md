# CLI Reference

Detailed reference for all `twrp.exe` commands and options.

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
  - [--cleanup-uninstall](#--cleanup-uninstall)
  - [--install-magisk-hook](#--install-magisk-hook)
  - [--repaire-magisk-hook](#--repaire-magisk-hook)
  - [--uninstall-magisk-hook](#--uninstall-magisk-hook)
  - [--register-img / --unregister-img](#--register-img--unregister-img)
- [The `into` Keyword](#the-into-keyword)
- [Exit Codes](#exit-codes)
- [Environment Variables](#environment-variables)
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

**With debug:**

```cmd
twrp.exe --status --debug
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
4. Patches files into the cpio archive based on `patch.json` mapping
5. Writes the patched initrd.img back

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

**Installed-check gate (added after 4.1.0):** the flow refuses to flip the flag
when TWRP is not actually present in the image, and never touches
`recovery_flag` when it aborts:

* `twrp_support = false` → stops with
  `TWRP is NOT installed (twrp_support = false)` and points at
  `--install-twrp`
* required files missing (`twrp_missing()` non-empty) → stops with
  `TWRP install is incomplete - missing:` plus the list and points at
  `--repair-twrp`
* a stock image (no recovery system at all) → stops with
  `Stock WSA (no recovery system installed)`

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

Install the TWRP payload and mark it installed (`twrp_support = "true"`).
Added after 4.1.0 — `--enable-twrp` now requires it.

```cmd
twrp.exe --install-twrp
twrp.exe --install-twrp --path <initrd.img>
```

**What it does:**

1. Stops WSA when the live image is targeted (or patches the file directly)
2. Injects `assets/twrp.7z` through its `patch.json` map (`/init`,
   `/info.json`, `/sbin/`, `/twres/`, `/etc/`, `/system/lib64/`)
3. Sets `twrp_support` to `"true"` (logged as `twrp_support: false -> true`)
4. Reports what `twrp_missing()` still finds

**Notes:**

* Skips with `TWRP already installed, nothing to do` when the flag is already
  set, nothing is missing and you did not pass force (the GUI **Repair TWRP**
  button is the forced path; there is no `--force` flag)
* A placeholder or unreadable payload is reported as
  `Payload skipped: …` while the flag is still flipped — the flow then warns
  `WARNING: TWRP still incomplete - missing:` and tells you to fill
  `assets/twrp.7z` and run `--repair-twrp`
* On success it prints `TWRP installed successfully!` and points at
  `--enable-twrp`

---

### --repair-twrp

Force a re-injection of the TWRP payload and fix `twrp_support` (the
TWRP counterpart of `--repaire-magisk-hook`).

```cmd
twrp.exe --repair-twrp
twrp.exe --repair-twrp --path <initrd.img>
```

**What it does:**

1. Runs the install flow with `force=True` — the "already installed" short
   circuit is skipped, so `assets/twrp.7z` is injected again even when the
   flag was already `true`
2. Re-asserts `twrp_support = "true"`
3. Verifies with `twrp_missing()`; a missing/placeholder payload still ends
   in the `WARNING: TWRP still incomplete - missing:` report

Use it after `--enable-twrp` refuses with `TWRP install is incomplete`.

---

### --uninstall-twrp

Remove the TWRP files and folders from the image and clear both boot flags.

```cmd
twrp.exe --uninstall-twrp
twrp.exe --uninstall-twrp --path <initrd.img>
```

**What it does:**

1. Skips with `TWRP is not installed - nothing to remove` when neither the
   flag nor any TWRP entry is present
2. Deletes the payload files: `/sbin/twrp`, `/sbin/busybox`,
   `/sbin/linker64`, then the trees `/twres/`, `/etc/`, `/system/lib64/`
3. Puts the boot chain back: when `/init` is the regular dispatcher file and
   `lspinit` exists, it is replaced with the symlink `init -> lspinit`
   (`/init: dispatcher -> init -> lspinit`); without `lspinit` the file is
   kept
4. Sets `twrp_support = "false"` and — if it was on — `recovery_flag = "false"`
   (both transitions are logged, then `TWRP uninstalled`)

TWRP-specific directories are **removed entirely**: `twres/`, `etc/` and
`system/lib64/` only exist for the recovery payload in a WSA initrd. The
Magisk hook and the module images are not touched.

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

Open the **IMG Manager** — a 7-Zip-style browser/editor for the cpio archive
(extract, delete, rename, overwrite, edit, pack, back up, restore).

```cmd
twrp.exe --gui
twrp.exe --gui --path D:\initrd.img
```

**What it does:**

1. Creates the Qt application (before any dialog, so error boxes work)
2. Selects the image: `--path` → `<WSA>\Tools\initrd.img` → file dialog
3. Lists the cpio entries; if the live image is unreadable it offers one of its
   `*.img.bak-YYYYMMDD-HHMMSS` backups instead
4. Opens `ImgManagerWindow`, centred on the screen

See [IMG Manager](img-manager.md).

---

### --install-as-system-app

Install one or more APKs as system apps into an LSP module image.

```cmd
twrp.exe --install-as-system-app app.apk
twrp.exe --install-as-system-app a.apk b.apk
twrp.exe --install-as-system-app app.apk --path D:\initrd.img
```

**Behaviour:**

| Step | Detail |
|:-----|:-------|
| Mode | `--user` by default; `--admin` switches (and prompts for a password) |
| Target | `overlay.d/sbin/lsp_wsa-installer[-user].img` inside `initrd.img` |
| Boot hook | auto-installed if missing (see [Magisk Hook](magisk-hook.md)) |
| Permissions | privileged / default permission XMLs written into the module |

Exit codes: `0` success, `1` failure (file missing, password refused, stock
image), `2` bad usage.

---

### --update-as-system-app

Same as `--install-as-system-app`, but **forces** an overwrite of an app that is
already inside the module image (`force_update=True`).

```cmd
twrp.exe --update-as-system-app app.apk
twrp.exe --update-as-system-app app.apk --admin
```

---

### --admin / --user

Select which module image the following command operates on.

```cmd
twrp.exe --install-as-system-app app.apk --admin     # ADMIN (password required)
twrp.exe --install-as-system-app app.apk --user      # USER  (default)
twrp.exe --list-of-boltware --user
twrp.exe --admin --user                              # usage error, exit 2
```

| Flag | Image | `module.prop` id | Password |
|:-----|:------|:-----------------|:---------|
| `--admin` | `lsp_wsa-installer.img` | `wsa-installer` | ✅ required |
| `--user` | `lsp_wsa-installer-user.img` | `wsa-installer-user` | ❌ none |

The two flags are **mutually exclusive**. Default for install/update is
`--user`. `--status` always reports both images.

Each image also carries its own `module.prop` `name` and a one-line
`description` (from `IMAGE_SPECS["admin"|"user"]["description"]`) that states
what the module is for — see
[Admin & User Modules](admin-user-modules.md). It is written when the image is
created (`create_lsp_image()`), so an already-existing image keeps its old text
until it is re-created.

**Password handling** (only for `--admin`): SHA-256 comparison, up to 3
attempts, non-interactive override via the `WSA_ADMIN_PASSWORD` environment
variable. See [Admin & User Modules](admin-user-modules.md).

---

### --list-of-boltware

List the system apps stored in the module image(s).

```cmd
twrp.exe --list-of-boltware            # both images (default)
twrp.exe --list-of-boltware --admin    # ADMIN image only
twrp.exe --list-of-boltware --user     # USER image only
```

Output is sectioned per image with an `[admin]` / `[user]` label. `NOT PRESENT`
means that image has never been created (not an error). Requires an injected
(non-stock) image.

---

### --uninstall-boltware

Schedule removal of system apps on the next boot.

```cmd
twrp.exe --uninstall-boltware com.wsa.webdav   # one package
twrp.exe --uninstall-boltware com.a com.b      # several
twrp.exe --uninstall-boltware                  # no arg = whole image
twrp.exe --uninstall-boltware --user           # USER image only
```

Packages are collected from every selected image, de-duplicated, written to
`overlay.d/sbin/uninstall.txt` **once**, and the boot handler in
`post-fs-data.sh` is (re)written. Nothing is removed until WSA reboots.
After that boot has removed the app, clear the list with
[`--cleanup-uninstall`](#--cleanup-uninstall) (next section).

See [Boltware Manager](boltware-manager.md).

---

### --cleanup-uninstall

Delete `overlay.d/sbin/uninstall.txt` (the pending uninstall list) from the
image. Added after 4.1.0.

```cmd
twrp.exe --cleanup-uninstall
twrp.exe --cleanup-uninstall --path <initrd.img>
```

**Why it exists:** the boot handler deletes only its *runtime copy* of
`uninstall.txt` — the archive entry inside `initrd.img` survives every
reboot, so the same list runs on **every** boot. Reinstalling the app days
later would have it uninstalled again on the next boot.

Run it **once after the boot that applied an uninstall** (the removal is
logged next to the handler, see `post-fs-data.log`). The handler in
`post-fs-data.sh` stays — it is a harmless no-op without the file and remains
ready for the next `--uninstall-boltware`.

GUI: the **Uninstall temp cleanup** button (IMG Manager, hook row, right
side); it shows the package names it cleared.

---

### --install-magisk-hook

Install the Magisk/boot hook infrastructure only — no TWRP rebuild, opens the
same windowed flow with `force=False`.

```cmd
twrp.exe --install-magisk-hook
twrp.exe --install-magisk-hook --path D:\initrd.img
```

Skips (and says so) when `overlay.d/sbin/post-fs-data.sh` already exists.
Requires `assets/fix.7z` and `assets/7z.exe`.

---

### --repaire-magisk-hook

Force a **full rebuild** of the hook from `fix.7z`, discarding whatever is
already installed (`force=True`).

```cmd
twrp.exe --repaire-magisk-hook
twrp.exe --repair-magisk-hook          # accepted alias
```

> The primary spelling keeps the historic typo `--repaire-magisk-hook`;
> `--repair-magisk-hook` maps to the same destination
> (`dest="repair_magisk_hook"`).

The result is verified with `hook_issues()` before reporting success.

---

### --uninstall-magisk-hook

Remove the boot hook and restore the stock boot chain. Added after 4.1.0.

```cmd
twrp.exe --uninstall-magisk-hook
twrp.exe --uninstall-magisk-hook --path <initrd.img>
```

**What it does:**

1. Skips with `Magisk hook is not installed - nothing to remove` when no
   hook entry is present
2. Restores `/init`: the hook's saved WSA init is renamed back —
   `wsainit -> init` (the current `/init` symlink/file is removed first).
   If `wsainit` is missing while `/init` is still a symlink the flow
   **aborts with a warning** (it cannot invent a bootable init) and removes
   nothing
3. Deletes the hook payload: `lspinit`, `magiskinit`,
   `overlay.d/init.lsp.magisk.rc`, `overlay.d/sbin/post-fs-data.sh`,
   `overlay.d/sbin/init-ld.xz`, `overlay.d/sbin/magisk.xz`,
   `overlay.d/sbin/stub.xz`, `overlay.d/sbin/uninstall.txt` and `.backup/`
4. Removes the rest of the **`overlay.d/` tree** — the directory exists only
   for the hook, so its module images (`lsp_*.img`) go with it
   (`/overlay.d/ tree removed`)

Finishes with `Magisk hook uninstalled (N entries removed)`.
`twrp_support` and `recovery_flag` are left untouched — combine with
`--uninstall-twrp` if you want the recovery system gone as well.

---

### --register-img / --unregister-img

Add or remove the Windows Explorer **`.img` → Open with → WSA IMG Manager**
registration (a `wsa-installer.img` ProgID, an `.img\shell\WsaInstallerImgManager`
verb, and — in frozen builds — `Applications\Twrp.exe`).

```cmd
twrp.exe --register-img
twrp.exe --unregister-img
```

* Writes under `HKLM\Software\Classes`, falling back to `HKCU`
* **Never** changes `.img`'s default handler (7-Zip, WinRAR keep working)
* Idempotent; both commands end with `SHChangeNotify`
* The app runs `--register-img` automatically on start (and via `--register-apk`)

See [Open With Registry](open-with-registry.md).

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
| 2 | Usage error — e.g. `--admin` and `--user` together, or an unknown option |

---

## Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `%TEMP%` | Temporary directory for extraction | `%TEMP%\twrp_temp\` |
| `%LOCALAPPDATA%` | WSA installation path | Auto-detected |
| `WSA_ADMIN_PASSWORD` | Password used by `--admin`, skipping the interactive prompt | *(unset → prompt)* |

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

### Batch Operations

```cmd
:: Inject and enable in one session
twrp.exe --inject twrp.7z
twrp.exe --enable-twrp
adb reboot recovery

:: Disable and verify
twrp.exe --disable-twrp
twrp.exe --status
adb reboot
```

### System-app management

```cmd
:: Install an app into the USER module (default, no password)
twrp.exe --install-as-system-app com.example.app.apk

:: Install into the ADMIN module (prompts for the password)
twrp.exe --install-as-system-app com.example.app.apk --admin

:: Overwrite an app that is already in the ADMIN module
twrp.exe --update-as-system-app com.example.app.apk --admin

:: See what is installed where (both module images)
twrp.exe --list-of-boltware

:: Schedule a removal for the next boot
twrp.exe --uninstall-boltware com.example.old

:: Full report
twrp.exe --status
```

### Hook maintenance

```cmd
:: Install the boot hook only
twrp.exe --install-magisk-hook

:: Force a full rebuild from fix.7z
twrp.exe --repaire-magisk-hook

:: Audit afterwards
twrp.exe --status
```

### IMG Manager and Explorer integration

```cmd
:: Open the archive editor
twrp.exe --gui
twrp.exe --gui --path D:\initrd.img

:: Register .img right-click / Open with
twrp.exe --register-img
twrp.exe --unregister-img
```

### Non-interactive admin install

```cmd
:: PowerShell / CI
$env:WSA_ADMIN_PASSWORD = "…"
twrp.exe --install-as-system-app app.apk --admin
```
