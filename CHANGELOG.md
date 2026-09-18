# Changelog

All notable changes to TWRP for WSA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [4.1.0] - 2026-09-18

### Added
- Full open-source CLI tool (`src/twrp.py`)
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
