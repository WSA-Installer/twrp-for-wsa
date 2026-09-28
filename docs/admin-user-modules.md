# Admin & User Modules

> Two independent LSP module images live inside `initrd.img`. Every system-app
> command in `twrp.py` can target either one, and the ADMIN one is protected by a
> password.

Added after `4.1.0`. Code: `twrp.py` (`IMAGE_SPECS`, `image_spec()`,
`select_image()`, `resolve_mode()`, `_require_admin_password()`).

---

## Why two images?

WSA's boot hook (`overlay.d/sbin/post-fs-data.sh`) mounts **every** file matching
`lsp_*.img` and runs that image's own `post-fs-data.sh`. So both modules coexist
without any shell modification: the mount is a wildcard, not a hard-coded name.

Which `/data/adb/modules/<id>` directory gets created on boot is decided by each
image's own `module.prop` `id` field — that is what separates them at runtime.

| | ADMIN module | USER module |
|---|---|---|
| Image (inside initrd) | `overlay.d/sbin/lsp_wsa-installer.img` | `overlay.d/sbin/lsp_wsa-installer-user.img` |
| `module.prop` id | `wsa-installer` | `wsa-installer-user` |
| `module.prop` name | `WSA Installer` | `WSA Installer (User)` |
| `module.prop` description | `WSA Installer - admin module: system apps and boot hook for WSA. Reason: the admin installs this TWRP module into the WSA image so the preinstalled system apps (bloatware) that power native Windows-Android integration - Termux shell, WebDAV share, CLI bridge - plus the boot hook that applies scheduled changes, are always part of the system image; access is protected by the --admin password.` | `WSA Installer (User) - user system apps for WSA. Reason: the same TWRP module system, but built and installed by the user for the system apps they choose to add as system apps; it lives in a separate image so those apps can be installed, updated or removed without touching the admin module and without any password.` |
| Temp workspace | `lsp_installer` | `lsp_installer_user` |
| Privileged-permission XML | `privapp-permissions-wsa-installer.xml` | `privapp-permissions-wsa-installer-user.xml` |
| Default-permission XML | `default-permissions-wsa-installer.xml` | `default-permissions-wsa-installer-user.xml` |
| Internal label | `admin` | `user` |
| Password required | ✅ yes | ❌ no |

The table is the literal content of `IMAGE_SPECS` in `twrp.py`.

---

## Mode resolution and the default

```python
def resolve_mode(mode, default="user"):
    if mode in ("admin", "user"):
        return mode
    return default
```

* `--admin` and `--user` are declared in a **mutually exclusive** argparse group —
  passing both exits with code 2.
* `install_as_system_app()` calls `resolve_mode(mode, "user")`, so **install and
  update default to the USER module** when no flag is given.
* The module-level globals (`LSP_MOD_ID`, `LSP_MOD_NAME`, `LSP_PRIV_XML`,
  `LSP_DEF_XML`, `LSP_LABEL`) are re-pointed by `select_image(mode)` — a single
  call that switches every LSP helper (has / extract / repack / find / create).

### Behaviour matrix

| Command | No flag | `--admin` | `--user` |
|---|---|---|---|
| `--install-as-system-app` | USER module | ADMIN module (password) | USER module |
| `--update-as-system-app` | USER module | ADMIN module (password) | USER module |
| `--list-of-boltware` | **both images** | ADMIN only | USER only |
| `--uninstall-boltware` | **both images** | ADMIN only | USER only |
| `--status` | **both images** | **both images** | **both images** |

`--status` always prints both modules (it loops `for m in ("admin", "user")`),
because status is a read-only report — the flags only gate *write* operations.

---

## The ADMIN password gate

`--admin` runs `_require_admin_password()` **before any file is opened**:

1. If the environment variable `WSA_ADMIN_PASSWORD` is set, it is hashed and
   compared. On success the prompt is skipped (useful for automation); on a
   mismatch it falls back to the interactive prompt.
2. Otherwise `getpass.getpass("Enter the password: ")` is shown — **3 attempts**
   (`ADMIN_PASSWORD_ATTEMPTS`), then the operation is cancelled with
   `Too many failed attempts - admin install cancelled.`
3. Comparison is `hashlib.sha256(entered).hexdigest() == ADMIN_PASSWORD_SHA256`.
   The plaintext password is never written to the source tree or to a file.

`Ctrl+C` / `EOF` at the prompt aborts cleanly (`Password required for --admin.`).

> The expected digest lives in `twrp.py` as `ADMIN_PASSWORD_SHA256`. Treat it as
> a local convenience lock, **not** as a security boundary: anyone with read
> access to the source can read the digest, and SHA-256 is not a password KDF.

### Automation

```bash
WSA_ADMIN_PASSWORD="…" twrp.py --install-as-system-app app.apk --admin
```

---

## Examples

```bash
# Install into the USER module (default, no password)
twrp.py --install-as-system-app com.example.app.apk

# Install into the ADMIN module (prompts for the password)
twrp.py --install-as-system-app com.example.app.apk --admin

# Update/overwrite an app already inside the ADMIN module
twrp.py --update-as-system-app com.example.app.apk --admin

# List system apps in the USER module only
twrp.py --list-of-boltware --user

# List system apps in both modules (default)
twrp.py --list-of-boltware

# Full report: WSA info + both module images
twrp.py --status

# Work against a detached image instead of the live WSA one
twrp.py --status --path C:\initrd.img
twrp.py --install-as-system-app app.apk --admin --path C:\initrd.img
```

Exit codes: `0` success, `1` failure (file not found, password refused, stock
image, WSA missing), `2` argparse usage error (e.g. `--admin --user` together).

---

## Code map (for maintainers)

| Symbol | Role |
|---|---|
| `IMAGE_SPECS` | the single source of truth for both modules |
| `image_spec(mode)` | returns the spec dict; anything ≠ `"admin"` falls back to `"user"` |
| `select_image(mode)` | re-points every `LSP_*` global at the chosen image |
| `resolve_mode(mode, default="user")` | CLI mode resolution |
| `_require_admin_password()` | SHA-256 gate, env override, 3 attempts |
| `WSATWRP.install_as_system_app(..., mode=)` | install / update, gates `--admin` |
| `WSATWRP.list_boltware(..., mode=)` | `None` → both images |
| `WSATWRP.uninstall_boltware(..., mode=)` | collects from selected images, de-duplicates |
| `WSATWRP.status()` | always reports both images |

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Wrong password (3/3)` | digest mismatch — the source's `ADMIN_PASSWORD_SHA256` is not the one you expect; pull the latest `twrp.py` |
| `Password required for --admin. Aborted.` | non-interactive shell + no `WSA_ADMIN_PASSWORD` |
| App installed but not visible | it landed in the *other* module — run `--list-of-boltware` (both) and check the `[admin]` / `[user]` label |
| `System Apps … NOT PRESENT` | that image was never created; run `--install-as-system-app` for that mode first |
| `Recovery system: STOCK (no TWRP)` | no injected image — inject TWRP first (`twrp.py --inject …`) |

See also: [Boltware Manager](boltware-manager.md) · [IMG Manager](img-manager.md) · [CLI Reference](cli-reference.md)
