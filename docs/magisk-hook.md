# Magisk Hook Infrastructure

> The boot-time hook that mounts `lsp_*.img`, runs each module's
> `post-fs-data.sh`, and uninstalls packages on demand.

Added after `4.1.0`. Code: `twrp.py` (`add_hook_infrastructure()`,
`hook_issues()`, `repair_hook_infrastructure()`, `override_hook_infrastructure()`,
`patch_postfsdata()`). CLI: `--install-magisk-hook`,
`--repaire-magisk-hook` (alias `--repair-magisk-hook`).

---

## What the hook consists of

| Entry inside `initrd.img` | Mode | Role |
|---|---|---|
| `overlay.d/` | `040750` | overlay root |
| `overlay.d/sbin/` | `040750` | scripts root |
| `overlay.d/sbin/post-fs-data.sh` | `0644` | early-boot entry point |
| `overlay.d/sbin/lspinit` | `0750` | LSP init |
| `overlay.d/sbin/magiskinit` | `0750` | Magisk init (root builds) |
| `overlay.d/sbin/wsainit` | `0777` | WSA init (root builds) |

(`HOOK_DIRS`, `HOOK_MODES`, `HOOK_DIR_MODE` in `twrp.py`.)

The script source is **`assets/fix.7z`** — extracted with the bundled
`assets/7z.exe` into `%TEMP%\twrp_temp\Initrd-fix`.

---

## The three operations

### 1. Add — `add_hook_infrastructure()`

* Fails if `assets/fix.7z` is missing.
* **Skips if the hook is already installed** (`overlay.d/sbin/post-fs-data.sh`
  present in the archive) and logs
  `Magisk already installed, skipping hook infrastructure`.
* Extracts `fix.7z` to `FIX_TEMP` and injects its tree into the image.

### 2. Audit — `hook_issues()`

Read-only. Returns a list of human-readable problems (empty = healthy):

* missing directory entries (`overlay.d/`, `overlay.d/sbin/`)
* directory entries out of order (a cpio archive requires parents before children)
* wrong permission bits on `lspinit` / `magiskinit` / `wsainit` / `post-fs-data.sh`
* missing or un-patched `post-fs-data.sh`

### 3. Repair / Override

| Function | Behaviour |
|---|---|
| `repair_hook_infrastructure()` | fixes exactly what `hook_issues()` reported; **safe to call repeatedly**, idempotent |
| `override_hook_infrastructure()` | **force**: deletes `overlay.d/sbin/post-fs-data.sh` and `.backup` (unless they still have children), then rebuilds everything from `fix.7z`. Returns `True` only if the result passes `hook_issues()` |

`patch_postfsdata(base)` normalises the script: strips the
`# shellcheck disable=SC2174` line and appends the
`# --- TWRP uninstall handler` block if `POSTFSDATA_MARKER` is not already there
(so the patch is applied at most once).

---

## CLI

```bash
# Install the hook only (GUI flow, no full TWRP rebuild)
twrp.py --install-magisk-hook

# Force a full rebuild from fix.7z, discarding whatever is installed
twrp.py --repaire-magisk-hook        # alias: --repair-magisk-hook

# Either against the live WSA image or a detached file
twrp.py --install-magisk-hook --path C:\initrd.img
```

Both flags launch the same windowed flow
(`_flow_install_magisk_hook(..., force=…)`): `force=False` for install,
`force=True` for repair. The flow reports each step in the log pane and detects
whether it is working on the live WSA recovery system or a standalone file.

> Note the flag spelling: the primary option is `--repaire-magisk-hook`
> (historic typo, kept for compatibility); `--repair-magisk-hook` is accepted as
> an alias.

---

## Uninstall-on-boot (how removals actually happen)

Removals are *scheduled*, not executed immediately:

1. `WSATWRP.patch_postfsdata_uninstall()` writes the handler into
   `overlay.d/sbin/post-fs-data.sh`. It appends a background block that waits for
   Android to finish booting, then processes the list. With `LOG_FOR_USER` it also
   copies the early log to
   `/storage/emulated/0/WSA Installer/post-fs-data.log`.
2. `WSATWRP.inject_uninstall_txt(packages)` writes
   `overlay.d/sbin/uninstall.txt` — one package per line.

On the next boot the handler consumes the list and removes those packages.
See [Boltware Manager](boltware-manager.md).

---

## Prerequisites

* TWRP injected (a **stock** image is rejected: `Recovery system: STOCK (no TWRP)`)
* `assets/fix.7z`
* `assets/7z.exe`
* WSA installed and detected, or `--path` given

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `fix.7z not found: …` | the asset is missing — restore `assets/fix.7z` |
| `Magisk already installed, skipping hook infrastructure` | normal; use `--repaire-magisk-hook` to force a rebuild |
| `Failed to rebuild Magisk hook!` | `override_hook_infrastructure()` could not re-add the tree — check `fix.7z` integrity |
| Hook present but apps not mounted | `hook_issues()` will name the wrong mode / missing dir; run `--repaire-magisk-hook` |
| Uninstall "did nothing" | removal happens on the **next boot**; check the log in `/storage/emulated/0/WSA Installer/` |

See also: [Admin & User Modules](admin-user-modules.md) · [Boltware Manager](boltware-manager.md) · [Flow](flow.md)
