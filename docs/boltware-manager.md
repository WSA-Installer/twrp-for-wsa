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
twrp.py --uninstall-boltware com.wsa.webdav      # one package
twrp.py --uninstall-boltware                     # no argument = whole image
twrp.py --uninstall-boltware com.a com.b --user  # several, USER image only
twrp.py --uninstall-boltware --admin             # ADMIN image only
```

### What happens

```
for m in (["admin", "user"] if mode is None else [mode]):
    select_image(m)
    pending.extend(self._uninstall_boltware_image(initrd, apk_name))
pending = list(dict.fromkeys(pending))        # de-duplicate, keep order
if pending:
    initrd.patch_postfsdata_uninstall()       # write the boot handler
    initrd.inject_uninstall_txt(pending)      # write uninstall.txt
    print(f"Uninstall scheduled for {len(pending)} package(s) on next boot")
    # + IMPORTANT note: run --cleanup-uninstall after the removal boot
```

Key points:

* Packages are **collected from every selected image**, then de-duplicated —
  an app installed in both modules is scheduled exactly once.
* `uninstall.txt` is injected **once**, with the merged list.
* Nothing is executed immediately: the handler added to
  `overlay.d/sbin/post-fs-data.sh` runs it on the next boot
  (see [Magisk Hook](magisk-hook.md)).
* `uninstall.txt` lives **inside the image** (RAMdisk) — the handler deletes
  only its runtime copy, so the archive entry re-runs the same list on every
  later boot. **After the removal boot, clear it** with
  `twrp.py --cleanup-uninstall` (GUI: **Uninstall temp cleanup**), otherwise a
  later reinstall is uninstalled again on the next boot.
* `apk_name` omitted → `_uninstall_boltware_image(initrd, None)` removes the
  entire module image (`overlay.d/sbin/lsp_wsa-installer[-user].img`).

---

## Typical session

```bash
twrp.py --status                                # WSA info + both modules
twrp.py --list-of-boltware                      # what is installed where
twrp.py --uninstall-boltware com.example.old    # schedule removal (both images)
twrp.py --list-of-boltware                      # image still listed until reboot
# ... reboot WSA ...
twrp.py --list-of-boltware                      # now gone
twrp.py --cleanup-uninstall                     # clear the pending list (do this!)
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Recovery system: STOCK (no TWRP)` | nothing injected yet — run `twrp.py --inject …` first |
| `WSA not found!` | WSA is not installed / not detected; pass `--path` |
| `File not found: …` | the `--path` image does not exist |
| Still listed after uninstall | expected — removal happens on the **next boot** |
| App removed from one module only | it exists in both; re-run without `--admin` / `--user` |
| `Uninstall scheduled for 0 package(s)` | the package name did not match any entry; check `--list-of-boltware` for the exact id |
| Reinstalled app disappears again on next boot | stale `uninstall.txt` re-ran — run `twrp.py --cleanup-uninstall` (GUI: **Uninstall temp cleanup**) after the removal boot |

See also: [Admin & User Modules](admin-user-modules.md) · [Magisk Hook](magisk-hook.md) · [Commands](commands.md)
