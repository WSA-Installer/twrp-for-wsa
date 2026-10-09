# Magisk Hook Infrastructure

> The boot-time hook that mounts `lsp_*.img`, runs each module's
> `post-fs-data.sh`, and uninstalls packages on demand.

Added after `4.1.0`. Code: `twrp.py` (`add_hook_infrastructure()`,
`hook_issues()`, `repair_hook_infrastructure()`, `override_hook_infrastructure()`,
`build_boot_script()`, `patch_postfsdata()`, `_flow_uninstall_magisk_hook()`). CLI:
`--install-magisk-hook`, `--repaire-magisk-hook` (alias `--repair-magisk-hook`),
`--uninstall-magisk-hook`.

---

## What the hook consists of

| Entry inside `initrd.img` | Mode | Role |
|---|---|---|
| `overlay.d/` | `040750` | overlay root |
| `overlay.d/sbin/` | `040750` | scripts root |
| `overlay.d/sbin/post-fs-data.sh` | `0644` | early-boot entry point |
| `overlay.d/sbin/wsa-playstore.sh` | `0755` | Play-Store system-app helper (background) |
| `overlay.d/sbin/webdavfs` | `0755` | static musl FUSE WebDAV client binary (HTTPS via mbedTLS) |
| `overlay.d/sbin/webdavfs.sh` | `0755` | WebDAV drive-mount reconciler (background) |
| `overlay.d/sbin/lspinit` | `0750` | LSP init |
| `overlay.d/sbin/magiskinit` | `0750` | Magisk init (root builds) |
| `overlay.d/sbin/wsainit` | `0777` | WSA init (root builds) |

(`HOOK_DIRS`, `HOOK_MODES`, `HOOK_DIR_MODE` in `twrp.py`.)

The hook **binaries** come from **`assets/fix.7z`** — extracted with the bundled
`assets/7z.exe` into `%TEMP%\twrp_temp\Initrd-fix`. The script itself is not
taken from `fix.7z`: every injection/repair rewrites `post-fs-data.sh` with the
canonical **debug build** produced by `build_boot_script()` (see
[Boot logging](#boot-logging)).

---

## Boot logging

The boot script writes to three places:

| Destination | Lifetime | How to read it |
|---|---|---|
| `$(dirname "$0")/post-fs-data.log` (tmpfs, `/sbin/post-fs-data.log`) | wiped next boot | visible in logcat for that boot |
| `/data/adb/lsp-boot.log` | **persistent across boots** | `adb root; adb shell cat /data/adb/lsp-boot.log` |
| `/storage/emulated/0/WSA Installer/post-fs-data.log` | copy of the above, refreshed after every boot | plain file access from Android (no root needed) |

The background handler copies the persistent log to the user path as soon as
Android reports `sys.boot_completed=1` — **no `--debug` flag needed** (the old
`LOG_FOR_USER` gate was removed). The inner module script
(`create_lsp_image()`) logs to the writable `/data/adb/module-post-fs-data.log`
instead of the read-only image mountpoint.

---

## Play Store system-app helper (`wsa-playstore.sh`)

A second script ships with the hook: `overlay.d/sbin/wsa-playstore.sh`
(`WSA_PLAYSTORE_SH` in `twrp.py`, injected by `inject_wsa_playstore_sh()`).
The canonical boot script ends with a launcher **below** the uninstall
handler that starts it in the background on every boot:

```sh
WSA_PS="$(dirname "$0")/wsa-playstore.sh"
if [ -f "$WSA_PS" ]; then
    chmod 755 "$WSA_PS"
    ( "$WSA_PS" ) &
fi
```

The helper is the root half of the *Play Store system-app promotion*
feature. The store app (`com.android.vending`, formerly `wsa.playstore`)
installs apps as **normal user apps** and only records intent in its
registry; the helper does everything privileged:

1. waits for `sys.boot_completed=1`, then loops every ~10 s (PID-guarded
   via `/data/adb/.wsa-playstore.pid`);
2. touch-tests `/system` for writability (`mount -o remount,rw` fallback —
   never `adb remount`); if not writable it only logs and retries;
3. reads `/data/data/com.android.vending/files/info.json` (pure
   `grep -oE`/`sed`, no jq) and processes every registered package:

| State | Action |
|---|---|
| `true` | skip forever |
| `"pending"` | `pm list packages -s` shows it → `true`; otherwise self-heal the copy/XML, stay `"pending"` |
| `false` | already system → `true`; `pm path` finds the APKs → copy base+splits into `/system/priv-app/<pkg>/`, append both XML blocks → `"pending"`; `pm path` fails → stay `false`, log |

4. permission XMLs (`privapp-permissions-wsa-playstore.xml`,
   `default-permissions-wsa-playstore.xml`) are **created with a header if
   missing**, appended before the closing tag with a `grep` dedupe per
   package — app 2's block lands below app 1's. Content comes from the
   embedded `PRIVILEGED_PERMS` / `DANGEROUS_PERMS`+`SPECIAL_PERMS` lists
   (same default profile as the installer). There is **no `pm install`** —
   the store already installed the app as a user app.

The registry contract (states, atomic-write rule, prompt-before-install,
"never touch `/system` or `/data/adb`") is documented for the store agent
in `CHANGELOG.md`. Helper log lines are prefixed `[SysApp]` and go to the
same three destinations as the boot script.

---

## WebDAV drive-mount helper (`webdavfs` + `webdavfs.sh`)

A second helper pair ships with the hook:

| Entry | Source | Role |
|---|---|---|
| `overlay.d/sbin/webdavfs` | `assets/webdavfs-x86_64` (injected by `inject_webdavfs_files()`) | static musl FUSE WebDAV client — full RW (PROPFIND / GET Range / PUT / DELETE / MKCOL / COPY / MOVE), Basic auth, optional HTTPS (mbedTLS 3.6.7 static), TTL cache, buffered writes, raw FUSE protocol |
| `overlay.d/sbin/webdavfs.sh` | `WEBDAVFS_SH` in `twrp.py` (injected by `inject_webdavfs_files()`) | reconciler — polls the registry and mounts/unmounts drives |

The canonical boot script ends with a launcher **below** the wsa-playstore
block that starts the reconciler in a new session (`setsid`) on every boot:

```sh
WD="$(dirname "$0")/webdavfs.sh"
if [ -f "$WD" ]; then
    chmod 755 "$WD"
    setsid sh "$WD" < /dev/null > /dev/null 2>&1 &
fi
```

**Connectivity contract — loopback ONLY.** From Windows after WSA starts:

```
adb reverse tcp:8085 tcp:8085
```

The reconciler polls `http://127.0.0.1:8085/info.json` every ~3 s. LAN /
host-IP discovery is **forbidden** — the binary and the shell script never
listen on or connect to a non-loopback address.

**Registry payload:**

```json
{
  "c": {"mount": true,  "path": "C:\\",  "sdcard": "C Drive"},
  "d": {"mount": false, "path": "D:\\",  "sdcard": "D Drive"}
}
```

| Field | Meaning |
|---|---|
| key | drive letter (single lowercase char `c`–`z`) |
| `mount` | GUI toggle — `true` = mount, `false` = unmount |
| `sdcard` | label shown under `/sdcard/` — `/` and `\` sanitized to `_`, empty → `<LETTER>: Drive` |

Each enabled drive is mounted as **USB-style external storage**:

1. FUSE mount at `/mnt/media_rw/<SHORT>` — short name derived from the
   `sdcard` label (alphanumeric + `._-`, max 16 chars, fallback to drive
   letter). `/mnt/media_rw/` is Android's secondary-volume root; file
   managers list entries there as external storage.
2. Symlink `/storage/<SHORT>` → `/mnt/media_rw/<SHORT>` — the path apps
   and file managers actually scan.
3. `MEDIA_MOUNTED` broadcast sent to both `/storage/<SHORT>` and `/sdcard`.

Mount options:
`allow_other,context=u:object_r:media_rw_data_file:s0`.

**Reconcile behaviour:**

1. waits for `sys.boot_completed=1`, then loops every ~3 s (PID-guarded
   via `/data/adb/webdavfs-daemon.pid`);
2. fetches the registry (`curl` or `wget`, 2 s connect / 5 s max);
3. for every letter `c`–`z`: mount `true` → mount (label change → unmount
   old short + remount new); mount `false` → unmount + remove symlink;
   absent from registry but present in the state file → unmount + state
   cleanup;
4. on **registry outage** mounts are **retained** (GRACE = 45 s, never
   force-unmount — protects unrelated bind-mounts). Logs
   `Registry grace exceeded; retaining mounts`.

State file: `/data/adb/webdavfs-state` (`<letter>=<shortname>` per line).
Logs `[WebDAV]` lines to the same three destinations as the boot handler.

**Binary smoke:** `webdavfs --version` prints `webdavfs-TLS-ENABLED` when
linked with mbedTLS; `--selftest` runs a namespace-aware XML parse + bounded
size scan; `-d` enables debug mode. CI guards fail the build if the binary
exceeds 200 KB **without** the `mbedtls` string (TLS stripped by mistake).

The registry contract and architecture are documented in
`https://github.com/WSA-Installer/webdav-client-WSA` (`docs/`).

---

## The four operations

### 1. Add — `add_hook_infrastructure()`

* Fails if `assets/fix.7z` is missing.
* **Skips the tree injection if the hook is already installed**
  (`overlay.d/sbin/post-fs-data.sh` present in the archive) and logs
  `Magisk already installed, skipping hook infrastructure`. Before skipping it
  compares the script against `build_boot_script()` and, when the installed
  copy is an older/lean version, rewrites it in place and logs
  `Upgraded post-fs-data.sh to the debug version`.
* Extracts `fix.7z` to `FIX_TEMP` and injects its tree into the image.

### 2. Audit — `hook_issues()`

Read-only. Returns a list of human-readable problems (empty = healthy):

* missing directory entries (`overlay.d/`, `overlay.d/sbin/`)
* directory entries out of order (a cpio archive requires parents before children)
* wrong permission bits on `lspinit` / `magiskinit` / `wsainit` / `post-fs-data.sh` / `wsa-playstore.sh` / `webdavfs` / `webdavfs.sh`
* a `post-fs-data.sh` that is not the current debug version
  (`… not the debug boot script (N bytes - old version, repair needed)`)
* a `wsa-playstore.sh` or `webdavfs.sh` that differs from the embedded copy
  (`… out of date (N bytes vs M - repair needed)`)
* a missing `webdavfs` binary when `assets/webdavfs-x86_64` exists

### 3. Repair / Override

| Function | Behaviour |
|---|---|
| `repair_hook_infrastructure()` | fixes exactly what `hook_issues()` reported; **safe to call repeatedly**, idempotent |
| `override_hook_infrastructure()` | **force**: deletes `overlay.d/sbin/post-fs-data.sh` and `.backup` (unless they still have children), then rebuilds everything from `fix.7z`. Returns `True` only if the result passes `hook_issues()` |

`patch_postfsdata(base)` upgrades **any** on-disk variant — the lean `fix.7z`
base, an old handler-only build, or an earlier full script — to the canonical
debug script from `build_boot_script()`. It is idempotent: feeding it the
canonical bytes returns them unchanged, which is exactly the equality
`hook_issues()` checks. The former `POSTFSDATA_UNINSTALL_BLOCK` /
`SHELLCHECK_LINE` / `POSTFSDATA_MARKER` constants were folded into the
builder.

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

1. `WSATWRP.patch_postfsdata_uninstall()` writes the canonical debug script
   (`build_boot_script()`) into `overlay.d/sbin/post-fs-data.sh`. It contains
   a background block that waits for Android to finish booting, then copies
   the persistent log to
   `/storage/emulated/0/WSA Installer/post-fs-data.log` and processes the
   list (this copy is **always** embedded — the old `LOG_FOR_USER` gate is
   gone).
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
again!). For the live WSA image `--uninstall-boltware` therefore verifies the
removal over adb (`pm list packages -s`) and **deletes `uninstall.txt`
automatically** once no selected package is still a system app. When that
automatic step is skipped (external `--path`, adb unavailable, timeout),
clear it manually: `twrp.py --cleanup-uninstall`
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
| `Magisk already installed, skipping hook infrastructure` | normal; the script is still checked and upgraded if stale; use `--repaire-magisk-hook` to force a full rebuild |
| `Failed to rebuild Magisk hook!` | `override_hook_infrastructure()` could not re-add the tree — check `fix.7z` integrity |
| Hook present but apps not mounted | `hook_issues()` will name the wrong mode / missing dir; run `--repaire-magisk-hook` |
| `… not the debug boot script (N bytes - old version, repair needed)` | an older (lean) script is installed — `--repaire-magisk-hook` rewrites it with full logging |
| No boot log anywhere | old scripts logged to a read-only path and printed nothing; reinstalling (or `--repaire-magisk-hook`) writes the debug version — then check `/data/adb/lsp-boot.log` (`adb root`) or `/storage/emulated/0/WSA Installer/post-fs-data.log` |
| Hook needs to go entirely | `--uninstall-magisk-hook` — restores `wsainit -> init`, removes the payload and the whole `overlay.d/` tree |
| Uninstall "did nothing" | removal happens on the **next boot**; check the log in `/storage/emulated/0/WSA Installer/` |
| Reinstalled app removed again on next boot | stale `uninstall.txt` still inside the image — run `twrp.py --cleanup-uninstall` after the removal boot |

See also: [Admin & User Modules](admin-user-modules.md) · [Boltware Manager](boltware-manager.md) · [Flow](flow.md)
