# Support

## Getting Help

### Documentation

- [Installation Guide](docs/installation.md) — Step-by-step installation instructions
- [CLI Commands Reference](docs/commands.md) — Full reference for all twrp.exe commands
- [Architecture](docs/architecture.md) — How TWRP for WSA works internally
- [Supported Images](docs/supported-images.md) — All 7 WSA variant details
- [Troubleshooting](docs/troubleshooting.md) — Common issues and solutions
- [FAQ](docs/faq.md) — Frequently asked questions

### Community

- [GitHub Issues](https://github.com/WSA-Installer/twrp-for-wsa/issues) — Bug reports and feature requests
- [GitHub Discussions](https://github.com/WSA-Installer/twrp-for-wsa/discussions) — Questions and community support
- [YouTube](https://www.youtube.com/@AT_Tech_Zone) — Video tutorials and guides

### Contact

- **Bug Reports**: [GitHub Issues](https://github.com/WSA-Installer/twrp-for-wsa/issues/new)
- **Feature Requests**: [GitHub Discussions](https://github.com/WSA-Installer/twrp-for-wsa/discussions)
- **Security Issues**: See [SECURITY.md](SECURITY.md)

## Frequently Asked Questions

### Is TWRP for WSA safe?

Yes. TWRP for WSA modifies only WSA's `initrd.img` and does not affect the host Windows system. The modification is reversible by disabling TWRP mode.

### Will this void my warranty?

No. TWRP for WSA works within WSA's sandbox and does not modify Windows system files. However, using recovery mode may affect WSA's normal operation.

### Can I use this with Magisk?

Yes. TWRP for WSA is compatible with Magisk-rooted WSA images. You can backup your rooted WSA installation before making changes.

### Will this work on ARM64?

Yes. WSA runs an x86_64 Linux kernel on all platforms, including ARM64 via binary translation. The TWRP binary is compiled for x86_64, which works on all platforms.

### Do I need ADB installed?

ADB is required for some operations (like connecting to TWRP recovery). However, the core inject and toggle commands work without ADB.

### What happens if WSA updates?

WSA updates replace the `initrd.img`. After an update, you'll need to re-inject TWRP:

```cmd
twrp.exe --inject twrp.7z
twrp.exe --enable-twrp
```

### Can I backup my WSA installation?

Yes. With TWRP running, you can create a full NANDroid backup via ADB:

```cmd
adb shell twrp backup
```

### How do I remove TWRP completely?

Disable TWRP mode and restart WSA:

```cmd
twrp.exe --disable-twrp
adb reboot
```

TWRP files remain in the initrd.img but are not used unless re-enabled.

## Troubleshooting

Before opening a new issue:

1. Check the [Troubleshooting Guide](docs/troubleshooting.md)
2. Search [existing issues](https://github.com/WSA-Installer/twrp-for-wsa/issues)
3. Run `twrp.exe --status --debug` and include the output

When opening a new issue, include:

- Windows version (e.g., Windows 11 22H2)
- WSA version (run `twrp.exe --status`)
- Steps to reproduce the problem
- Expected vs actual behavior
- Full output of `twrp.exe --status --debug`
