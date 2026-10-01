# Changelog

All notable changes to TWRP for WSA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- **Module images**: dual ADMIN (`lsp_wsa-installer.img`) and USER (`lsp_wsa-installer-user.img`) initrd images with mode-aware defaults
- `--admin` / `--user` mode flags; `--admin` is protected by a SHA-256 password gate (3 attempts, `WSA_ADMIN_PASSWORD` override)
- `--install-as-system-app` / `--update-as-system-app` — install or overwrite APKs inside a module image
- `--list-of-boltware` — list system apps in both images (union, de-duplicated, admin/user tags)
- `--uninstall-boltware` — schedule removal through `uninstall.txt` (applied on next boot)
- `--install-magisk-hook` / `--repaire-magisk-hook` — install, audit (`hook_issues()`) and force-rebuild the boot hook from `fix.7z`
- `--gui` — IMG Manager: 7-Zip-style browser for the `initrd.img` cpio archive with Extract → Edit → Pack, text editor, undo/redo and auto backups (`*.img.bak-YYYYMMDD-HHMMSS`)
- `--register-img` / `--unregister-img` — register `.img` → *Open with* → **WSA IMG Manager** in Explorer (HKLM, HKCU fallback)
- `prebuilt/init` — committed static ELF64 dispatcher binary + `prebuilt/SHA256SUMS`
- `.github/workflows/build-dispatcher.yml` — dispatcher-only CI build (musl-gcc, artifact + checksum)
- Bundled tools: `7z.exe`, `7z.dll`, `adb.exe`, `aaptpp.exe`, `img-checker.exe`, `img-creater.exe`, `cygwin1.dll`
- Icons: `icon.ico`, `twrp.ico`, `wsa_twrp_logo.png`
- Six new docs: `admin-user-modules`, `img-manager`, `open-with-registry`, `magisk-hook`, `boltware-manager`, `dispatcher`
- IMG Manager: **Extract selected** / **Extract all** in the archive viewer (multi-select tree, right-click *Select all / Invert / Clear*) and in the internal-image dialog — name-aware cpio, zip, tar and 7z extraction
- IMG Manager toolbar rows 2–3: **Info**, **Install/Update as system app** (+ **Admin** tick), **Enable/Disable TWRP**, **Install/Repair hook**, **Status**, **List/Uninstall system app**, **Register/Unregister `.img`**
- `--install-twrp` / `--repair-twrp` / `--uninstall-twrp` — TWRP payload lifecycle: inject `assets/twrp.7z` + `twrp_support=true` (no-op when already installed), force re-inject (`force=True`), and full removal (`/sbin/twrp`, `/twres/`, `/etc/`, `/system/lib64/` gone, `init -> lspinit` restored, `twrp_support` + `recovery_flag` cleared)
- `--uninstall-magisk-hook` — restore the stock boot chain: `wsainit` is renamed back to `/init` (aborts if it cannot), the hook payload and `.backup/` are deleted and the whole `overlay.d/` tree is removed — module images (`lsp_*.img`) included; TWRP flags stay untouched
- IMG Manager: **Install TWRP**, **Repair TWRP**, **Uninstall TWRP** and **Uninstall hook** buttons with confirmation dialogs; the toolbar grew to **four rows** (row 3 = TWRP lifecycle left / hook lifecycle right, row 4 = status/apps/`.img`), window height `H = 660 → 700`
- `--cleanup-uninstall` — delete `overlay.d/sbin/uninstall.txt` (the pending uninstall list) from the image. The boot handler only removes its runtime copy, so the archive entry re-ran the list on **every** later boot and would uninstall a reinstalled app again; run once after the removal boot. The handler in `post-fs-data.sh` stays (harmless no-op without the file). GUI: **Uninstall temp cleanup** button (row 3) with explanatory tooltip; `uninstall_boltware()` now prints the recommendation
- `assets/twrp.7z` placeholder shipped so `--install-twrp` runs before a real payload exists (reports `Payload skipped` instead of failing)
- `InitrdManager.get_twrp_support()` / `set_twrp_support()` — targeted `info.json` flag rewrite that preserves every other byte (entry may move to the end of the archive, harmless to the boot chain)
- `set_recovery_flag()` regex fallback for `info.json` layouts the same-length byte pairs do not match (spacing/quoting variants)
- `LogDialog` — scrolling transcript (timestamped, `Copy all`, `Save log…`) that runs any `_flow_*` on a worker thread and echoes every line to the terminal; `InfoDialog` for the one-shot Info report
- Admin tick: password prompt for Install/Update, `WSA_ADMIN_PASSWORD` override, 3 wrong attempts disable the tick for the session and the operation falls back to the user module
- Live-image guard: `_confirm_live()` warns about unapplied staged edits, `_after_live_change()` offers to reload the image after a CLI run modified it
- **Post-install verification now requires a SYSTEM install**: after starting WSA the system-app flow waits for `sys.boot_completed=1` and runs `pm list packages -s` for every installed APK (`ADBManager.verify_boot_and_packages()`), logging `Verified: <pkg> is installed as a SYSTEM app`, `NOT a system app: <pkg> is installed as USER app only` or `NOT visible yet: <pkg>` with the *reboot WSA once more* hint and the diagnostics path; boot can never be confirmed → `Verification skipped` (120 s cap, `adb connect 127.0.0.1:5555` retried while polling)
- `assets/fix.7z` in this repo re-synced from the parent distribution (was stale: 619-byte lean script, missing `stub.xz`, `magisk.xz`, `info.json`, `wsainit`)
- New smoke `boot_script_smoke.py` — canonical script content + `bash -n` syntax, patch idempotency, hook upgrade/repair, inner-script log path, verification stub (46 checks)
- **Permission inventory synced with the official Android reference** (`Manifest.permission`): `DANGEROUS_PERMS` 41→43 (adds `ACCESS_LOCAL_NETWORK`, `RANGING`; fixes the voicemail name to `com.android.voicemail.permission.ADD_VOICEMAIL`), `SPECIAL_PERMS` 16→17 (adds `FOREGROUND_SERVICE_SPECIAL_USE`), `NORMAL_PERMS` 136→164 (33 new documented normals; 5 misclassified entries moved out), `PRIVILEGED_PERMS` 47→70 (20 documented privileged + `BIND_WALLPAPER`/`CHANGE_CONFIGURATION`/`GLOBAL_SEARCH` reclassified); new display-only `SIGNATURE_PERMS` (26) and `GMS_PERMS` (4: GMS `AD_ID`, c2dm `RECEIVE`, `READ_GSERVICES`, `C2D_MESSAGE`) — 324 entries total, rendered greyed/locked in the permission manager and never pushed to `pm grant`
- **Interactive uninstall picker**: bare `--uninstall-boltware` now lists the module's packages numbered and accepts numbers (`1,3`) / a package name / `all` / `q` (`parse_uninstall_selection()` + `prompt_uninstall_selection()`); `--uninstall-boltware pkg1 pkg2` removes several packages in one run; the GUI *Uninstall system app* button replaced its single-text prompt with `PackageSelectDialog` (checkbox list, *Select all*, *Clear*, manual comma-separated entry)
- **Uninstall ADB verification + auto-cleanup**: for the live WSA image `uninstall_boltware()` now runs `_uninstall_auto_verify()` — starts WSA, waits for `sys.boot_completed=1`, polls `ADBManager.verify_system_removed()` (`pm list packages -s`) until no selected package is still a **system** app (a later *user* reinstall does not block success), stops WSA (`KillWSA.kill_all()`) and deletes `uninstall.txt` via the shared `_remove_uninstall_txt()` — no manual cleanup; external `--path`/failure keeps the `--cleanup-uninstall` fallback
- `WSATWRP.list_lsp_packages()` — programmatic package list of the module image(s) (data-returning twin of `list_boltware()`) feeding the CLI/GUI pickers
- New smoke `uninstall_picker_smoke.py` — picker parsing/prompt, `verify_system_removed` stubs (removed/still-system/boot-timeout), `_uninstall_auto_verify` skip/success/failure paths, `_remove_uninstall_txt`, `list_lsp_packages`, multi-package uninstall
- **Play-Store system-app promotion (`wsa-playstore.sh`)** — the hook now ships a standalone root helper at `overlay.d/sbin/wsa-playstore.sh` (`WSA_PLAYSTORE_SH`, injected idempotently by `inject_wsa_playstore_sh()` from add/repair/override, audited by `hook_issues()` as `missing entry` / `out of date`, launched in the background by a `wsa-playstore` block appended **below** the uninstall handler in `post-fs-data.sh` via `$(dirname "$0")`). The store installs the app as a **normal user app** and only writes a registry entry; every `/system` change happens on the next boots: the helper waits for `sys.boot_completed=1`, touch-tests the Magisk `/system` mount for rw (remount fallback — never `adb remount`), copies base+split APKs from `pm path` into `/system/priv-app/<package>/` (644/755, `chown 0:0`, `chcon system_file`), appends a `<privapp-permissions>` block and an `<exception>` block to `system/etc/permissions/privapp-permissions-wsa-playstore.xml` and `system/etc/default-permissions/default-permissions-wsa-playstore.xml` (grep-dedupe per package, content from the embedded `PRIVILEGED_PERMS` + `DANGEROUS_PERMS`/`SPECIAL_PERMS` lists — the same default profile the installer uses when no permission window is answered), flips the registry flag to `pending`, and marks it `true` after `pm list packages -s` verifies the system install on the following boot. **No `pm install` anywhere.** Logs `[SysApp]` lines to the same three destinations as the boot handler; ~10 s loop, PID-guarded, pure `sh` (busybox/toybox applets, no jq/adb)
- **`info.json` registry contract for the Play Store agent** (applicationId `wsa.playstore`, being renamed to `com.android.vending`): file **`/data/data/com.android.vending/files/info.json`**, a single append-only JSON object `{"<pkg>": false, "<pkg2>": "pending", "<pkg3>": true}` — **bool `false`** (agent: prompt the user **before** the normal install; on Yes install as user app and append `"pkg": false`, atomic write: temp file in the same directory + replace, scalar values only), **string `"pending"`** (written by the root helper after the APK+XML copy — reboot pending), **bool `true`** (helper verified `pm list -s`). Entries are **never removed**; the helper rewrites the file in place (preserves the app-owned inode, so the agent keeps read/write access). The agent must **never touch `/system` or `/data/adb`** — root work is exclusively the helper's

### Changed
- **The install path now writes one canonical *debug* boot script** (`build_boot_script()` is the single source of truth used by `patch_postfsdata()`, hook injection/repair/override and `patch_postfsdata_uninstall()`): full `[Root]` logging everywhere, persistent `/data/adb/lsp-boot.log` (`adb root`), and the background handler **unconditionally** copies it to `/storage/emulated/0/WSA Installer/post-fs-data.log` after boot — the `LOG_FOR_USER` gate (and the `LOG_FOR_USER`, `POSTFSDATA_UNINSTALL_BLOCK`, `POSTFSDATA_MARKER`, `SHELLCHECK_LINE` constants) is removed; install, repair and uninstall all emit identical bytes
- `add_hook_infrastructure()` no longer skips a stale script silently: when `post-fs-data.sh` already exists it is compared with `build_boot_script()` and upgraded in place (`Upgraded post-fs-data.sh to the debug version`); `hook_issues()` reports `… not the debug boot script (N bytes - old version, repair needed)`
- The inner module script (`create_lsp_image()`) logs to the writable `/data/adb/module-post-fs-data.log` — previously it appended to the read-only image mountpoint (`$(dirname "$0")/post-fs-data.log`), so **module staging never produced a log**
- **`--uninstall-boltware` (and the *Uninstall system app* button) no longer touch the ADMIN image by default**: with no flag (GUI: Admin tick off) the run targets the **USER** image only and prints `Module: USER image (default - use --admin for the admin image)`; the button now goes through `_admin_gate()` like install/update, names the module in its confirm dialog and title, and passes an explicit `mode=`. Removing from both modules = run twice (plain, then `--admin`). `--list-of-boltware` / `--status` still report both modules (read-only)
- `twrp.py` moved from `src/twrp.py` to the repository root
- **`--uninstall-boltware` argument semantics**: `nargs='*'` — explicit package names remove those packages (a list is now supported end-to-end), `all` (or the picker's `all`) removes the whole module image, and the bare flag opens the **interactive picker** instead of silently deleting the whole image (breaking change vs. the old `nargs='?'` behaviour); the epilog/help show all four forms
- The *Uninstall system app* GUI button runs the picker + multi-package selection through `_admin_gate()`/`_confirm_live()` as before, but its confirmation now names `N package(s)` and mentions the automatic adb verification
- `_flow_cleanup_uninstall()` delegates the file handling to the shared `WSATWRP._remove_uninstall_txt()` (same messages, plus `No manual cleanup needed - …` on the auto-verified path)
- The permission manager window renders the two new greyed, locked categories (`signature`, `gms`) — they are excluded from `get_result()` profiles, so install profiles are unchanged
- **`--enable-twrp` now checks that TWRP is actually installed** before flipping `recovery_flag`: `twrp_support=false` stops with `TWRP is NOT installed …` + `--install-twrp` hint, missing files stop with the `twrp_missing()` list + `--repair-twrp` hint; `recovery_flag` is never touched when the gate aborts
- Uninstall hooks **remove the whole `overlay.d/` tree** (not just the script files) — the directory only exists for the hook, so `lsp_*.img` module images go with it
- `--status` now reports both module images alongside the WSA/initrd state
- Documentation rewritten to describe the full 24-option CLI surface

### Fixed
- **Install/Update as system app no longer crashes** with `'PermissionManagerWindow' object has no attribute 'exec'` (introduced with the GUI button rows): `_collect_profiles()` now shows the frameless `QWidget` and spins a `QEventLoop` that `result_ready` quits — the same pattern the CLI path always used; the window is centred on screen
- `PermissionManagerSignals.result_ready` changed from `Signal(dict)` to `Signal(object)`: `Signal(dict)` could not carry the **Cancel** result `None` (Shiboken conversion error, the slot received `{}` instead) — Cancel/close now correctly fall back to the default permission profile in **both** the GUI and CLI install paths
- `PermissionManagerWindow.closeEvent` emits the cancelled result once when the window is closed without OK/Cancel (Alt+F4), so the caller's event loop can never hang
- **System-app permission XMLs are merged instead of replaced**: `privapp-permissions-wsa-installer[-user].xml` and `default-permissions-wsa-installer[-user].xml` now hold one `<privapp-permissions>` / `<exception>` block per package, rebuilt from `permissions/<pkg>.json` (`regenerate_permission_xmls()`) — installing a second system app no longer wipes the first app's package name; `--uninstall-boltware` drops only the removed package's block; `fixed=` is tracked per package instead of shared; legacy blocks without a profile are preserved; malformed files are rebuilt instead of crashing
- Dispatcher build split from the 180-minute TWRP workflow into `build-dispatcher.yml`
- **Log-dialog flood protection**: `LogDialog` now collapses consecutive duplicate messages — the transcript rewrites the last line with a live `×N` counter instead of appending N copies (`_replace_last_block()`), runaway leading whitespace (> 4 spaces) is clamped to 4, the terminal echo prints a repeating line only on the first occurrence and at ×10/×100/×1000/×10000, and `_finish()` resets the counter — a `Module: USER image` line repeated hundreds of times now shows as a single `×450` entry instead of flooding the dialog

### Removed
- `src/twrp.py` (replaced by root-level `twrp.py`)

---

## [4.1.0] - 2026-09-18

### Added
- Full open-source CLI tool (`twrp.py`)
- `--inject` command for 7z extraction + cpio injection
- `--inject-file` for single file injection with `into` keyword
- `--inject-folder` for folder injection with `into` keyword
- `--enable-twrp` / `--disable-twrp` for boot flag toggle
- `--status` with WSA version, recovery flag, twrp support, amazon support, note
- `--path` for custom initrd.img location
- `--debug` for verbose output
- Custom dispatcher ELF binary (`init.c`)
- `info.json` metadata with string-format flags
- `patch.json` cpio injection map
- GitHub Actions automated TWRP build
- Complete documentation (installation, commands, architecture, supported images, troubleshooting)
- Source-Available / Community-Extension License
- Contributing guide

### Changed
- `info.json` fields are strings (not booleans) for cross-platform compatibility
- Recovery flag supports both capitalized and lowercase variants (`"True"`/`"true"`, `"False"`/`"false"`)
- Flag replacement uses same-length byte padding (trailing space) for in-place cpio patching

### Fixed
- Flag toggle now handles both `"True"` and `"true"` variants
- Exit code propagation from `make` through `tee` in build pipeline

---

## [4.0.0] - 2026-09-15

### Added
- Initial TWRP for WSA implementation
- Boot chain dispatcher
- Basic inject/extract functionality
- WSA initrd.img cpio patching

---

## [3.0.0] - 2026-09-10

### Added
- Project planning and architecture design
- WSA image variant analysis (7 variants)
- GitHub Actions build workflow

---

## [2.0.0] - 2026-09-05

### Added
- Concept design for TWRP recovery in WSA
- Boot chain analysis
- CpioUtils implementation

---

## [1.0.0] - 2026-09-01

### Added
- Project initialization
- WSA Installer integration planning
