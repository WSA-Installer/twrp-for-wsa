# IMG Manager (Archive Editor)

> A 7-Zip-style manager for the `initrd.img` cpio archive — browse, extract,
> edit, rename, delete, pack, back up and restore, all without leaving the app.

Added after `4.1.0`. Entry point: `twrp.py --gui` (`WSATWRP.manage_img()`).

---

## Entry points

| How | What happens |
|---|---|
| `twrp.py --gui` | picks the live WSA image (`<WSA>\Tools\initrd.img`), falls back to a file dialog |
| `twrp.py --gui --path C:\initrd.img` | opens that file directly (error dialog if missing) |
| Explorer → right-click `.img` → **Open with** → *WSA IMG Manager* | same GUI, path passed via `--path "%1"` — see [Open With Registry](open-with-registry.md) |
| Corrupt / unreadable live image | offers to load one of its `*.img.bak-*` backups instead |

`manage_img()` creates the `QApplication` **before** any `QMessageBox` /
`QFileDialog` call — required because the right-click path can reach an error
dialog before the main window exists.

---

## The dialogs

| Class | Purpose |
|---|---|
| `ImgManagerWindow` | main frameless window: four toolbar rows, multi-column multi-select tree, status line, persistent **no-backup warning** |
| `ArchiveViewerDialog` | opens an archive that lives *inside* the image — **Extract selected / Extract all → Edit → Pack** |
| `NestedImgDialog` | an internal `.img` inside the archive (extract with `img-checker.exe`, repack with `img-creater.exe`) — also has **Extract selected / Extract all** |
| `ScriptEditorDialog` | plain-text edit of a file entry with mode preservation |
| `LogDialog` | scrolling transcript for one CLI operation (`Copy all` / `Save log…`), runs the operation on a worker thread |
| `InfoDialog` | the same transcript shell, filled in one go — the **Info** report |

### Supported archive kinds

`ArchiveViewerDialog` sniffs the payload (`sniff()`, `_open_kind()`):

* **cpio** — native, the primary format of `initrd.img`
* **gzip / xz / bz2** — via the Python stdlib, including when they wrap a cpio or tar
* **tar**, **zip** — via `tarfile` / `zipfile`
* **7z** — through the bundled `assets/7z.exe`
* anything else → read-only hex/text viewer (`_open_unknown`)

Rebuild helpers: `build_cpio_from_dir()`, `build_tar_from_dir()`,
`build_zip_from_dir()` — each restores uid/gid 0, empty uname/gname, directory
modes (`0o040750` class), symlinks and per-file permission bits
(`_file_perms()` / `guess_mode()`).

### Selective extraction (Extract selected / Extract all)

Both viewers run on `QAbstractItemView.ExtendedSelection` trees, so Ctrl/Shift
click (and Ctrl+A) pick the rows to write out:

* `ArchiveViewerDialog._on_extract(selected_only)` — `_selected_names()` +
  `_expand_names()` (a ticked **folder** pulls in every entry under it; 7-Zip
  backslash paths and stdlib slash paths are both handled), then one backend:

  | container | call |
  |---|---|
  | cpio | `CpioUtils.extract_to(path, dest, names)` — already name-aware |
  | zip | `ZipFile.extractall(path=dest, members=names)` |
  | tar | `TarFile.extractall(dest, members=names, filter="data")` |
  | 7z | `7z x -o<dest> -y <archive> <name…>` (`_run()`) |

* `_on_tree_menu()` — right-click **Extract selected…**, **Extract all…**,
  **Select all**, **Invert selection**, **Clear selection**
* `NestedImgDialog._on_extract()` — copies the ticked rows (or the whole
  unpacked tree) out with `shutil.copytree` / `copy2`, reporting the file count
* an empty selection explains itself instead of silently dumping the archive

### Extract → Edit → Pack flow

1. `_act_extract` unpacks to a temp tree (`_stage_temp`, `_rebuild_from_dir`)
2. `_act_edit` / `_act_add_file` / `_act_add_folder` / `_act_rename` /
   `_act_delete` operate on the tree
3. `_act_apply` repacks from the tree (`_rebuild`, `_commit_bytes`) — a
   `_commit_op` records the new bytes in the staging area
4. Only **Apply** touches the staged image; the live image changes when the
   staged image is committed back

For an internal `.img`, `img-checker.exe` unpacks and `img-creater.exe` packs —
the exact pair `InitrdManager.extract_lsp_image()` / `repack_lsp_image()` already
use. Everything happens in a temp folder.

### History (undo / redo)

* `_after_history_change`, `_reset_history`, `_undo`, `_redo`
* `_push_snapshot` / `_load_snapshot` keep a snapshot stack
* `_update_dirty` tracks unsaved state; `closeEvent` warns on dirty exit

---

## CLI buttons (rows 2–4)

Row 1 keeps the file operations (extract, delete, rename, overwrite, add,
new folder, refresh + Undo/Redo). Three more rows expose every CLI argument
that makes sense while an image is open — `_CLI_ACTIONS` drives the buttons
and `_on_cli()` dispatches to `self._cli_<key>()`:

| Row | Button | Handler | Runs |
|---|---|---|---|
| 2 | **Info** | `_cli_info()` | `_build_info_text()` in an `InfoDialog`: path, size, mtime, sha256, staged/backups state, cpio census (folders/files/symlinks + unpacked size), recovery system + `info.json`, Magisk hook state (`hook_issues()`), both module images, WSA path/running |
| 2 | **Install as system app…** | `_cli_install_system_app(False)` | APK picker → `PermissionManagerWindow` per package → `_flow_install_system_app` |
| 2 | **Update as system app…** | `_cli_install_system_app(True)` | same flow with `force_update=True` |
| 2 | **☐ Admin** | `_admin_gate()` | password gate for the two buttons above |
| 2 | **Enable TWRP** / **Disable TWRP** | `_cli_enable()` / `_cli_disable()` | `_flow_enable` (installed-check gate) / `_flow_disable` |
| 3 | **Install TWRP** / **Repair TWRP** | `_cli_install_twrp()` / `_cli_repair_twrp()` | `_flow_install_twrp(force=False/True)` — inject `twrp.7z` + `twrp_support=true` |
| 3 | **Uninstall TWRP** | `_cli_uninstall_twrp()` | confirm (`wsainit`/`overlay.d` are *not* touched) → `_flow_uninstall_twrp` (removes `/sbin/twrp`, `/twres/`, `/etc/`, `/system/lib64/`, `init -> lspinit`, clears both flags) |
| 3 | **Install hook** / **Repair hook** | `_cli_install_hook()` / `_cli_repair_hook()` | `_flow_install_magisk_hook(force=False/True)` |
| 3 | **Uninstall hook** | `_cli_uninstall_hook()` | confirm (explains `wsainit -> init` and that the whole `overlay.d/` tree — module images included — goes) → `_flow_uninstall_magisk_hook` |
| 4 | **Status** | `_cli_status()` | `WSATWRP.status()` |
| 4 | **List system apps** | `_cli_list_apps()` | `list_boltware()` (admin + user modules) |
| 4 | **Uninstall system app…** | `_cli_uninstall_app()` | package-name prompt → `uninstall_boltware()` |
| 4 | **Register .img** / **Unregister .img** | `_cli_register_img()` / `_cli_unregister_img()` | `register_img_handler()` / `unregister_img_handler()` |

### How a button runs

* `_flow_*` flows (`log, window, **args`) run on a worker thread through
  `LogDialog.run_flow()` — **every line lands in the dialog and is echoed to
  the terminal** by `LogDialog.log()`, the same `log()` contract
  `WSATWRP._launch_gui()` uses
* print-only CLI functions (`status`, `list_boltware`, `uninstall_boltware`,
  `register_img_handler`, `unregister_img_handler`) go through
  `LogDialog.run_printing()`, which swaps `sys.stdout` for a `_LineTee` that
  forwards each complete line to the dialog + terminal
* the dialog stays open after `request_close()` so the transcript can be read,
  copied or saved; on close, `finished` → `_after_live_change()`

### Admin tick

1. tick **Admin**, press **Install/Update** → password prompt
   (`QInputDialog`, `EchoMode.Password`), SHA-256 against
   `ADMIN_PASSWORD_SHA256`; `WSA_ADMIN_PASSWORD` is honoured first
2. right password → the flow runs with `mode="admin"` (the `_flow_*` never
   re-asks, so the dialog prompt is the only one)
3. wrong password → `ADMIN_PASSWORD_ATTEMPTS` (3) tries with a warning each
   time; on the 3rd miss the tick is **unchecked and disabled for the session**
   and the operation **proceeds as the USER module**
4. cancelling the prompt runs nothing
5. tick off → straight to `mode="user"`, no prompt

### Live-image guard

The buttons operate on the **live** image while this window edits a staged
copy, so:

* `_confirm_live()` warns before the run when the staging area is dirty
* after the dialog closes, `_after_live_change()` hashes the live file and —
  if it changed — offers to reload it (staged edits discarded)

---

## Backups

* Every save of the live image writes a sibling file:
  `<name>.img.bak-YYYYMMDD-HHMMSS`
* `_choose_backup_file()` lists those siblings and lets you pick one
* The status line carries a persistent **no-backup warning** while you work
* If the live image is unreadable, `manage_img()` offers to open a backup
  instead of failing (`Open IMG Manager from backup: <backup> -> <live>`)

Restore:

```bash
# list backups
dir C:\...\Tools\initrd.img.bak-*

# restore by hand (outside the app)
copy /Y "C:\...\Tools\initrd.img.bak-20260928-101500" "C:\...\Tools\initrd.img"
```

---

## UI details

* Custom-painted frameless shell in the same idiom as `PermissionManagerWindow`,
  with standard Qt widgets inside
* Multi-select tree with context menu (`_on_context_menu`), double-click open
  (`_on_double_click`), drag/size grip (`resizeEvent`, `_update_control_rects`)
* Toolbar rows: (1) open, refresh, add file, add folder, new folder, rename,
  delete, extract, edit, apply, backup, restore (`_act_*`); (2) info, install /
  update system app + Admin tick, enable / disable TWRP; (3) install / repair /
  uninstall TWRP, install / repair / uninstall hook; (4) status, list /
  uninstall system app, register / unregister `.img` (`_cli_*`)
* `wheelEvent` / `_max_scroll` / `_hit` handle tree scrolling; `_fill`,
  `_refresh_buttons`, `_update_status` keep the chrome in sync
* Keyboard: `keyPressEvent` (Enter opens, Delete removes, F5 refreshes)

---

## Requirements

| Asset | Needed for |
|---|---|
| `assets/7z.exe` **and** `assets/7z.dll` | 7z archives (`7z.exe` alone cannot load its codec) |
| `assets/img-checker.exe` | unpack internal `.img` |
| `assets/img-creater.exe` | repack internal `.img` |
| `assets/fix.7z` | Magisk hook rebuild (see [Magisk Hook](magisk-hook.md)) |
| `assets/icon.ico` / `assets/twrp.ico` | window / Open-with icon |

Missing `img-checker.exe` / `img-creater.exe` produce an explicit message:
*"… is missing from assets/ — this image cannot be edited."*

> `assets/twrp.7z` (the auto-inject payload) is **not** shipped in this
> repository. Auto-inject detects its absence and skips; use
> `--inject <file>.7z` with your own payload.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Codec Load Error: …\assets\7z.dll` when opening a 7z entry | `assets/7z.dll` is missing next to `7z.exe` — copy it back (the archive then falls back to an error dialog) |
| `Not a readable cpio image: …` | not a cpio — try opening an archive entry inside it, or load a backup |
| `Empty cpio image.` | truncated file; the backup picker opens automatically |
| `img-creater.exe could not pack this image` | the unpacked tree changed shape (missing `./` entries) — re-extract |
| Nothing happens after Apply | Apply stages the change; you must also commit it back to the live image |
| GUI exits immediately | no display available (`twrp.py --gui` needs a desktop session) |

See also: [Commands](commands.md) · [Open With Registry](open-with-registry.md) · [Flow](flow.md)
