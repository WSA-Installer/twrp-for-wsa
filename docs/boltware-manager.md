# Boltware Manager (system apps)

> List and remove the system apps that live inside the LSP module images.

Added after `4.1.0`. Code: `twrp.py` (`list_boltware()`, `_list_lsp_apps()`,
`uninstall_boltware()`, `_uninstall_boltware_image()`). CLI:
`--list-of-boltware`, `--uninstall-boltware`, `--cleanup-uninstall`.

"Boltware" is this project's term for apps baked into the recovery image as
system apps.

---

## Listing

```bash
twrp.py --list-of-boltware                # both module images (default)
twrp.py --list-of-boltware --admin        # ADMIN image only
twrp.py --list-of-boltware --user         # USER image only
twrp.py --list-of-boltware --path C:\initrd.img
```

Behaviour:

* Works on the live WSA image or `--path`.
* Rejects a stock image (`Recovery system: STOCK (no TWRP)`) — there is nothing
  to list.
* With no flag it loops `for m in ("admin", "user")`, calling `select_image(m)`
  then `_list_lsp_apps(initrd)` for each, so the output is clearly sectioned by
  `[admin]` / `[user]`.
* `System Apps (lsp_wsa-installer.img) [admin]: NOT PRESENT` means that module
  image has never been created — not an error.

---

## Removing

```bash
twrp.py --uninstall-boltware com.wsa.webdav      # one package (USER image - the default)
twrp.py --uninstall-boltware com.a com.b          # several packages at once
twrp.py --uninstall-boltware                      # interactive picker (numbers/name/all/q)
twrp.py --uninstall-boltware all                  # every USER system app (whole image)
twrp.py --uninstall-boltware --admin com.x        # one package, ADMIN image (gate)
twrp.py --uninstall-boltware --admin              # picker over the ADMIN image (gate)
```

The **interactive picker** (bare flag) prints the packages of the selected
module image numbered, then accepts: numbers (`1,3`), a package name, `all`
(= whole image) or `q` (cancel). The GUI **Uninstall system app** button
shows the same packages as a checkbox list with *Select all* and a manual
entry line — any combination can be selected in one run.

### What happens

```
modes = ["user"] if mode is None else [mode]     # default: USER image only
print("Module: USER image (default - use --admin for the admin image)")
for m in modes:
    select_image(m)
    # apk_name: None (whole image) | "pkg" | ["pkg1", "pkg2", ...]
    pending.extend(self._uninstall_boltware_image(initrd, apk_name))
pending = list(dict.fromkeys(pending))        # de-duplicate, keep order
if pending:
    initrd.patch_postfsdata_uninstall()       # write the boot handler
    initrd.inject_uninstall_txt(pending)      # write uninstall.txt
    print(f"Uninstall scheduled for {len(pending)} package(s) on next boot")
    # live WSA image only:
    #   start WSA -> wait for boot -> poll `pm list packages -s` until no
    #   selected package is still a SYSTEM app -> stop WSA -> auto-delete
    #   uninstall.txt ("No manual cleanup needed")
    # external --path / not verified -> the --cleanup-uninstall note below
```

Key points:

* Packages are collected from the **selected module image only** — USER by
  default, ADMIN only with `--admin`. A plain run never extracts or repacks
  the ADMIN image; to remove an app from both modules, run twice (plain, then
  `--admin`). `--list-of-boltware` / `--status` still report both modules.
* `uninstall.txt` is injected **once**, with that module's list.
* Nothing executes immediately: the handler added to
  `overlay.d/sbin/post-fs-data.sh` runs the list on the next boot
  (see [Magisk Hook](magisk-hook.md)).
* **Automatic verification (live WSA image):** after the image is patched,
  `_uninstall_auto_verify()` starts WSA, waits for `sys.boot_completed=1`,
  then polls `adb shell pm list packages -s <pkg>` until no selected package
  is still a **system** app (a package reinstalled afterwards as a plain
  user app does *not* block success). On success it stops WSA and deletes
  `overlay.d/sbin/uninstall.txt` itself — **no manual cleanup needed**.
* **Manual fallback:** for an external `--path` image, when WSA cannot be
  started or the timeout (120 s) passes, `uninstall.txt` is kept for safety
  and the `--cleanup-uninstall` note is printed — run it after the removal
  boot, otherwise a later reinstall is uninstalled again on the next boot.
* `apk_name` omitted (or `all` in the picker) →
  `_uninstall_boltware_image(initrd, None)` removes the entire module image
  (`overlay.d/sbin/lsp_wsa-installer[-user].img`).

---

## Typical session

```bash
twrp.py --status                                # WSA info + both modules
twrp.py --list-of-boltware                      # what is installed where
twrp.py --uninstall-boltware com.example.old    # schedule removal (USER image)
# ... WSA starts, the removal is verified over adb, WSA stops again,
#     uninstall.txt is deleted automatically ...
twrp.py --list-of-boltware                      # gone after the removal boot
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Recovery system: STOCK (no TWRP)` | nothing injected yet — run `twrp.py --inject …` first |
| `WSA not found!` | WSA is not installed / not detected; pass `--path` |
| `File not found: …` | the `--path` image does not exist |
| Still listed after uninstall | expected — removal happens on the **next boot** |
| App still present in the other module | one run targets one module only — repeat for the other module (`--admin`, or plain for USER); also expect removal only after the **next boot** |
| `Uninstall scheduled for 0 package(s)` | the package name did not match any entry; check `--list-of-boltware` for the exact id |
| Picker prints `No packages in this module image` | the selected module has no system apps — type the package name manually (GUI: manual entry line) |
| `Verification skipped: WSA boot not confirmed` | adb/WSA unavailable — `uninstall.txt` kept; run `--cleanup-uninstall` after the removal boot |
| `Not verified within the timeout` | the boot handler did not remove the package in 120 s — `uninstall.txt` kept for safety; reboot and re-check, then `--cleanup-uninstall` |
| Reinstalled app disappears again on next boot | stale `uninstall.txt` re-ran — run `twrp.py --cleanup-uninstall` (GUI: **Uninstall temp cleanup**) after the removal boot (only possible when the automatic cleanup was skipped) |

See also: [Admin & User Modules](admin-user-modules.md) · [Magisk Hook](magisk-hook.md) · [Commands](commands.md)
