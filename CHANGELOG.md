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
- **Post-install verification**: after starting WSA the system-app flow waits for `sys.boot_completed=1` and runs `pm list packages` for every installed APK (`ADBManager.verify_boot_and_packages()`), logging `Verified: <pkg> is installed and visible` or `NOT visible yet: <pkg>` with the *reboot WSA once more* hint and the diagnostics path; boot can never be confirmed → `Verification skipped` (120 s cap, `adb connect 127.0.0.1:5555` retried while polling)
- `assets/fix.7z` in this repo re-synced from the parent distribution (was stale: 619-byte lean script, missing `stub.xz`, `magisk.xz`, `info.json`, `wsainit`)
- New smoke `boot_script_smoke.py` — canonical script content + `bash -n` syntax, patch idempotency, hook upgrade/repair, inner-script log path, verification stub (46 checks)

### Changed
- **The install path now writes one canonical *debug* boot script** (`build_boot_script()` is the single source of truth used by `patch_postfsdata()`, hook injection/repair/override and `patch_postfsdata_uninstall()`): full `[Root]` logging everywhere, persistent `/data/adb/lsp-boot.log` (`adb root`), and the background handler **unconditionally** copies it to `/storage/emulated/0/WSA Installer/post-fs-data.log` after boot — the `LOG_FOR_USER` gate (and the `LOG_FOR_USER`, `POSTFSDATA_UNINSTALL_BLOCK`, `POSTFSDATA_MARKER`, `SHELLCHECK_LINE` constants) is removed; install, repair and uninstall all emit identical bytes
- `add_hook_infrastructure()` no longer skips a stale script silently: when `post-fs-data.sh` already exists it is compared with `build_boot_script()` and upgraded in place (`Upgraded post-fs-data.sh to the debug version`); `hook_issues()` reports `… not the debug boot script (N bytes - old version, repair needed)`
- The inner module script (`create_lsp_image()`) logs to the writable `/data/adb/module-post-fs-data.log` — previously it appended to the read-only image mountpoint (`$(dirname "$0")/post-fs-data.log`), so **module staging never produced a log**
- **`--uninstall-boltware` (and the *Uninstall system app* button) no longer touch the ADMIN image by default**: with no flag (GUI: Admin tick off) the run targets the **USER** image only and prints `Module: USER image (default - use --admin for the admin image)`; the button now goes through `_admin_gate()` like install/update, names the module in its confirm dialog and title, and passes an explicit `mode=`. Removing from both modules = run twice (plain, then `--admin`). `--list-of-boltware` / `--status` still report both modules (read-only)
- `twrp.py` moved from `src/twrp.py` to the repository root
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
