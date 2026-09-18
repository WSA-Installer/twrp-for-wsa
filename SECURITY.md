# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability within TWRP for WSA, please send an email to **[https://github.com/WSA-Installer/twrp-for-wsa/issues](https://github.com/WSA-Installer/twrp-for-wsa/issues)**. All security vulnerabilities will be promptly addressed.

**Please do not report security vulnerabilities through public GitHub issues.**

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 1 week
- **Fix or mitigation**: within 2 weeks for critical vulnerabilities

## Security Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Security Layers                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Layer 1: init.c Dispatcher                         │
│  ├── Case-insensitive recovery_flag check            │
│  ├── Static ELF binary (no dependencies)             │
│  └── Minimal attack surface                         │
│                                                      │
│  Layer 2: info.json Validation                      │
│  ├── String-based flags (not executable)             │
│  ├── Same-length byte replacement                    │
│  └── JSON format validation                         │
│                                                      │
│  Layer 3: Cpio Archive Integrity                    │
│  ├── Direct cpio manipulation                        │
│  ├── No external tools required                      │
│  └── Atomic file operations                         │
│                                                      │
│  Layer 4: WSA Isolation                             │
│  ├── Runs within WSA sandbox                        │
│  ├── No host system modification                     │
│  └── Recovery mode only (no persistent changes)     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## Security Considerations

### What TWRP for WSA does

- Modifies WSA's `initrd.img` to inject TWRP recovery files
- Adds a dispatcher binary that decides boot path at startup
- Provides recovery mode for backup, restore, and maintenance

### What TWRP for WSA does NOT do

- Modify the host Windows system
- Install persistent rootkits or backdoors
- Access network during boot (except ADB for recovery operations)
- Modify system partitions outside of WSA

### Best practices

- Always keep TWRP for WSA updated to the latest version
- Verify checksums of downloaded releases
- Use ADB only from trusted hosts
- Review info.json contents before injection
- Backup important data before enabling TWRP recovery

## Scope

This security policy applies to:

- The `twrp.exe` CLI tool
- The `init.c` dispatcher source code
- The `src/twrp.py` injector script
- GitHub Actions build workflows

This security policy does NOT apply to:

- TWRP itself (report to [TeamWin](https://twrp.me))
- WSA (report to Microsoft)
- ADB (report to Google/Android)
