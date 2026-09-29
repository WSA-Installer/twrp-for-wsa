# Magisk Hook Infrastructure

> The boot-time hook that mounts `lsp_*.img`, runs each module's
> `post-fs-data.sh`, and uninstalls packages on demand.

Added after `4.1.0`. Code: `twrp.py` (`add_hook_infrastructure()`,
`hook_issues()`, `repair_hook_infrastructure()`, `override_hook_infrastructure()`,
`patch_postfsdata()`, `_flow_uninstall_magisk_hook()`). CLI:
`--install-magisk-hook`, `--repaire-magisk-hook` (alias `--repair-magisk-hook`),
`--uninstall-magisk-hook`.

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

## The four operations

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

### 4. Remove — `_flow_uninstall_magisk_hook()` (added after 4.1.0)

Reverses the install in one pass:

1. **Restores `/init`** — the hook put the real WSA init aside as `wsainit`
   and replaced `/init` with a symlink. The flow removes `/init` and renames
   `wsainit -> init`. Safety rule: when `wsainit` is missing while `/init` is
   still a symlink it **aborts without removing anything** (there is no way to
   reconstruct a bootable init)
2. **Deletes the payload** — `lspinit`, `magiskinit`,
   `overlay.d/init.lsp.magisk.rc`, `overlay.d/sbin/post-fs-data.sh`,
   `init-ld.xz`, `magisk.xz`, `stub.xz`, `uninstall.txt` and `.backup/`
3. **Removes the whole `overlay.d/` tree** — the directory only exists for
   the hook, so module images (`lsp_*.img`) are removed with it

No-op with `Magisk hook is not installed - nothing to remove`; ends with
`Magisk hook uninstalled (N entries removed)`. The TWRP flags
(`twrp_support`, `recovery_flag`) are **not** touched — use
`--uninstall-twrp` for the recovery system itself.

---

## CLI

```bash
# Install the hook only (GUI flow, no full TWRP rebuild)
twrp.py --install-magisk-hook

# Force a full rebuild from fix.7z, discarding whatever is installed
twrp.py --repaire-magisk-hook        # alias: --repair-magisk-hook

# Remove the hook entirely (wsainit becomes /init again, overlay.d/ goes)
twrp.py --uninstall-magisk-hook

# Clear the pending uninstall list (run after the boot that applied it)
twrp.py --cleanup-uninstall

# Either against the live WSA image or a detached file
twrp.py --install-magisk-hook --path C:\initrd.img
twrp.py --uninstall-magisk-hook --path C:\initrd.img
twrp.py --cleanup-uninstall --path C:\initrd.img
```

Install and repair launch the same windowed flow
(`_flow_install_magisk_hook(..., force=…)`): `force=False` for install,
`force=True` for repair. Uninstall runs `_flow_uninstall_magisk_hook()`.
Each flow reports every step in the log pane and detects whether it is
working on the live WSA recovery system or a standalone file.

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

**How the handler finds the list**: it uses
`UNINSTALL_FILE="$(dirname "$0")/uninstall.txt"` — always *next to itself*,
never the image root. `init.lsp.magisk.rc` runs the script as
`sh ${MAGISKTMP}/post-fs-data.sh`, and the archive's `overlay.d/sbin/*` is
overlaid onto that ramdisk location, so the lookup resolves to
`${MAGISKTMP}/uninstall.txt` (`/sbin/uninstall.txt`) — the runtime copy of
archive `overlay.d/sbin/uninstall.txt`, exactly where `--uninstall-boltware`
writes it and `--cleanup-uninstall` deletes it.

The handler deletes only its **runtime copy** — `uninstall.txt` itself lives
inside `initrd.img`, so the archive entry survives every reboot and the same
list would run again on the next boot (a later reinstall would be removed
again!). **After the removal boot, clear it**: `twrp.py --cleanup-uninstall`
(GUI: **Uninstall temp cleanup** button), which deletes the file from the
image and leaves the handler in place (a harmless no-op without the list).

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
| Hook needs to go entirely | `--uninstall-magisk-hook` — restores `wsainit -> init`, removes the payload and the whole `overlay.d/` tree |
| Uninstall "did nothing" | removal happens on the **next boot**; check the log in `/storage/emulated/0/WSA Installer/` |
| Reinstalled app removed again on next boot | stale `uninstall.txt` still inside the image — run `twrp.py --cleanup-uninstall` after the removal boot |

See also: [Admin & User Modules](admin-user-modules.md) · [Boltware Manager](boltware-manager.md) · [Flow](flow.md)
