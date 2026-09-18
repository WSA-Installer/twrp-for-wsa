# Developer Guide

How to contribute to TWRP for WSA.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Conventions](#code-conventions)
- [Building](#building)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)

---

## Getting Started

TWRP for WSA is an open-source project. We welcome contributions of all kinds:

- Bug fixes
- New features
- Documentation improvements
- Code reviews
- Testing

## Development Setup

### Prerequisites

| Requirement | Version |
|:------------|:--------|
| Python | 3.10+ |
| PySide6 | 6.5+ |
| Windows | 10 (build 19041+) or 11 |
| WSA | Installed and functional |
| ADB | Platform tools installed |
| Git | Latest version |

### Clone the Repository

```bash
git clone https://github.com/WSA-Installer/twrp-for-wsa.git
cd twrp-for-wsa
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run from Source

```bash
# Check status
python src/twrp.py --status

# Inject TWRP
python src/twrp.py --inject twrp.7z

# Enable TWRP
python src/twrp.py --enable-twrp
```

## Project Structure

```
twrp-for-wsa/
├── src/
│   └── twrp.py              # Main CLI tool (~1500 lines)
├── docs/
│   ├── installation.md      # Installation guide
│   ├── commands.md          # CLI reference
│   ├── architecture.md      # How it works internally
│   ├── flow.md              # Boot and inject flow
│   ├── cli-reference.md     # Detailed CLI reference
│   ├── developer-guide.md   # This file
│   ├── adb.md               # ADB commands for TWRP
│   ├── variants.md          # WSA image variants
│   ├── supported-images.md  # All 7 WSA variant details
│   ├── troubleshooting.md   # Common issues and fixes
│   └── faq.md               # Frequently asked questions
├── assets/
│   └── twrp.png             # Project logo
├── .github/
│   ├── workflows/
│   │   └── build-twrp.yml   # GitHub Actions build workflow
│   └── PULL_REQUEST_TEMPLATE.md
├── init.c                   # Dispatcher source (compiled to ELF with musl-gcc)
├── info.json                # TWRP metadata template
├── patch.json               # Cpio injection map
├── requirements.txt         # Python dependencies
├── LICENSE.md              # Source-Available / Community-Extension License
├── CONTRIBUTING.md          # Contribution guidelines
├── CODE_OF_CONDUCT.md       # Code of conduct
├── SECURITY.md              # Security policy
├── SUPPORT.md               # Support and FAQ
├── ROADMAP.md               # Planned features
├── CHANGELOG.md             # Version history
└── README.md                # Project overview
```

## Code Conventions

### Python Style

- Follow PEP 8
- Use type hints where appropriate
- Use docstrings for public functions
- Keep functions under 50 lines where possible

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new injection method
fix: resolve flag toggle issue
docs: update installation guide
refactor: simplify cpio parsing
test: add unit tests for CpioUtils
```

### Branch Naming

- `feature/description` — New features
- `fix/description` — Bug fixes
- `docs/description` — Documentation changes
- `refactor/description` — Code refactoring

## Building

### Build TWRP Recovery Image

The TWRP recovery image is built automatically via GitHub Actions:

1. Go to [Actions](https://github.com/WSA-Installer/twrp-builder-wsa/actions)
2. Click **Build TWRP x86_64 for WSA**
3. Click **Run workflow**
4. Wait ~60 minutes
5. Download `twrp-x86_64-wsa` artifact

### Build twrp.exe

```bash
# Using Nuitka
pip install nuitka
python -m nuitka --standalone --output-filename=twrp.exe src/twrp.py

# Using PyInstaller
pip install pyinstaller
pyinstaller --onefile src/twrp.py --name twrp.exe
```

### Build Dispatcher

The dispatcher is compiled from `init.c` using `musl-gcc`:

```bash
# On Linux (GitHub Actions)
sudo apt-get install musl-tools
musl-gcc -static -o init init.c
```

## Testing

### Manual Testing

1. Check status: `python src/twrp.py --status`
2. Inject TWRP: `python src/twrp.py --inject twrp.7z`
3. Enable TWRP: `python src/twrp.py --enable-twrp`
4. Reboot WSA: `adb reboot recovery`
5. Verify TWRP boots
6. Disable TWRP: `python src/twrp.py --disable-twrp`
7. Reboot WSA: `adb reboot`
8. Verify Android boots

### Test Checklist

- [ ] Status shows correct WSA version
- [ ] Injection completes without errors
- [ ] Flag toggle works (enable/disable)
- [ ] TWRP boots when enabled
- [ ] Android boots when disabled
- [ ] ADB connects in recovery mode
- [ ] Custom `--path` works
- [ ] Debug output is verbose

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Update documentation if needed
6. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines.
