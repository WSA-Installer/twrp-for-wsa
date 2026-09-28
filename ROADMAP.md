# Roadmap

Planned features and improvements for TWRP for WSA.

---

## Current Release

### v4.1.0 (Current)

- Open-source CLI tool (`twrp.py`)
- TWRP injection via cpio patching
- Recovery flag toggle (`--enable-twrp` / `--disable-twrp`)
- Custom dispatcher ELF binary (init.c)
- GitHub Actions automated build
- Support for 7 WSA image variants
- Case-insensitive recovery_flag check
- info.json metadata system
- ADMIN / USER module images with password-gated `--admin`
- System-app install / update / list / uninstall (`boltware`)
- Magisk hook install / repair
- IMG Manager (`--gui`) with archive Edit/Pack and backups
- `.img` Open-with registration (`--register-img`)
- Compiled `prebuilt/init` + dispatcher-only CI workflow

---

## Planned

### v4.2.0

- Automatic WSA version detection
- Initrd.img compression support (gzip, lz4)
- Progress bar for injection operations
- Verbose logging mode
- `assets/twrp.7z` bundled payload for one-command injection

### v4.3.0

- GUI wrapper for twrp.exe (PySide6)
- Drag-and-drop 7z injection
- One-click backup and restore
- WSA image variant auto-detection
- Multi-language support

### v5.0.0

- Full TWRP integration (no manual initrd.img patching)
- Automatic WSA update handling
- Cloud backup support
- Plugin system for custom recovery tools
- Cross-platform support (Linux, macOS)

---

## Ideas

- Integration with WSA Installer for seamless setup
- Automated Magisk root detection
- Custom TWRP theme builder
- Recovery mode auto-start on WSA crash
- Network boot support for recovery

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to this project.
