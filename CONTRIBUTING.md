# Contributing to TWRP for WSA

Thank you for your interest in contributing to TWRP for WSA! This document provides guidelines and information for contributors.

---

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

---

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report, please check [existing issues](https://github.com/WSA-Installer/twrp-for-wsa/issues) to avoid duplicates.

When creating a bug report, include:

- **Clear title** — Describe the issue concisely
- **TWRP for WSA version** — Found via `twrp.exe --status`
- **WSA version** — e.g., 2404.40000.2.0
- **Windows version** — e.g., Windows 11 23H2
- **Steps to reproduce** — Detailed steps to trigger the bug
- **Expected behavior** — What you expected to happen
- **Actual behavior** — What actually happened
- **Debug output** — Run `twrp.exe --status --debug` and paste output

### Suggesting Features

Feature suggestions are welcome! Please provide:

- **Problem statement** — What problem does this solve?
- **Proposed solution** — How should it work?
- **Alternatives considered** — Other approaches you thought about

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test thoroughly on Windows 10 and/or Windows 11
5. Commit with a descriptive message
6. Push to your fork
7. Open a Pull Request

---

## Development Setup

### Prerequisites

- Python 3.10+
- Windows 10/11
- WSA installed and functional
- ADB platform tools
- Administrator privileges

### Getting Started

```bash
# Clone the repository
git clone https://github.com/WSA-Installer/twrp-for-wsa.git
cd twrp-for-wsa

# Install dependencies
pip install -r requirements.txt

# Run
python src/twrp.py --status
```

### Project Structure

```
twrp-for-wsa/
├── src/
│   └── twrp.py              # Main CLI tool (open source)
├── docs/
│   ├── installation.md      # Installation guide
│   ├── commands.md          # CLI reference
│   ├── architecture.md      # How it works
│   ├── supported-images.md  # WSA variant details
│   └── troubleshooting.md   # Common issues
├── assets/
│   └── twrp.png             # Project logo
├── init.c                   # Dispatcher source (compiled to ELF)
├── info.json                # TWRP metadata template
├── patch.json               # Cpio injection map
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
├── CONTRIBUTING.md          # This file
├── README.md                # Project documentation
└── .github/
    └── workflows/
        └── build-twrp.yml   # GitHub Actions build
```

---

## Code Style

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use meaningful variable and function names
- Add docstrings for public functions and classes
- Keep functions focused and concise

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <description>

Types:
  feat     - New feature
  fix      - Bug fix
  docs     - Documentation changes
  style    - Code style changes (formatting, etc.)
  refactor - Code refactoring
  perf     - Performance improvements
  test     - Adding or updating tests
  build    - Build system changes
  ci       - CI/CD changes
  chore    - Maintenance tasks

Scopes:
  cli      - Command line interface
  inject   - Initrd injection
  boot     - Boot/dispatcher
  docs     - Documentation
  build    - Build pipeline
```

Examples:
```
feat(cli): add --inject-file command
fix(inject): handle gzipped initrd.img
docs(readme): update installation guide
build(actions): fix lunch target format
```

### Branch Naming

- `feature/description` — New features
- `fix/description` — Bug fixes
- `docs/description` — Documentation changes
- `release/version` — Release preparation

---

## Testing

### Manual Testing

Before submitting a PR, test the following flows:

1. **Status Check** — `twrp.exe --status` works
2. **Inject** — `twrp.exe --inject twrp.7z` succeeds
3. **Enable/Disable** — Flag toggles correctly
4. **TWRP Boot** — TWRP loads after enable + reboot
5. **Android Boot** — Android loads after disable + reboot
6. **ADB** — Can connect in both modes

### Test Checklist

- [ ] Tested on Windows 10 (build 19041+)
- [ ] Tested on Windows 11
- [ ] Tested with at least one WSA image variant
- [ ] ADB connection works in both modes
- [ ] No Python errors or warnings
- [ ] Documentation updated if needed

---

## Building

### Development

```bash
python src/twrp.py --status
```

### TWRP Recovery Image (GitHub Actions)

The TWRP recovery image is built automatically via GitHub Actions:

1. Go to [Actions](https://github.com/gshellmr-code/twrp-builder-wsa/actions)
2. Click **Build TWRP x86_64 for WSA**
3. Click **Run workflow**
4. Download artifact from the completed run

---

## Documentation

- Update `docs/` if adding new features
- Update `README.md` if changing public API or behavior
- Follow the existing documentation style (badges, tables, mermaid diagrams)

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

## Questions?

If you have questions about contributing, feel free to:

- Open a [Discussion](https://github.com/WSA-Installer/twrp-for-wsa/issues)
- Contact via [YouTube](https://www.youtube.com/@AT_Tech_Zone)

Thank you for contributing to TWRP for WSA!
