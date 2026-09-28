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
- Bundled tools: `7z.exe`, `adb.exe`, `aaptpp.exe`, `img-checker.exe`, `img-creater.exe`, `cygwin1.dll`
- Icons: `icon.ico`, `twrp.ico`, `wsa_twrp_logo.png`
- Six new docs: `admin-user-modules`, `img-manager`, `open-with-registry`, `magisk-hook`, `boltware-manager`, `dispatcher`

### Changed
- `twrp.py` moved from `src/twrp.py` to the repository root
- `--status` now reports both module images alongside the WSA/initrd state
- Documentation rewritten to describe the full 19-option CLI surface
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
