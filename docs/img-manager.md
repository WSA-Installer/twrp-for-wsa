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

## The four dialogs

| Class | Purpose |
|---|---|
| `ImgManagerWindow` | main frameless window: toolbar, multi-column multi-select tree, status line, persistent **no-backup warning** |
| `ArchiveViewerDialog` | opens an archive that lives *inside* the image — **Extract → Edit → Pack** |
| `NestedImgDialog` | an internal `.img` inside the archive (extract with `img-checker.exe`, repack with `img-creater.exe`) |
| `ScriptEditorDialog` | plain-text edit of a file entry with mode preservation |

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
* Toolbar actions: open, refresh, add file, add folder, new folder, rename,
  delete, extract, edit, apply, backup, restore (`_act_*`)
* `wheelEvent` / `_max_scroll` / `_hit` handle tree scrolling; `_fill`,
  `_refresh_buttons`, `_update_status` keep the chrome in sync
* Keyboard: `keyPressEvent` (Enter opens, Delete removes, F5 refreshes)

---

## Requirements

| Asset | Needed for |
|---|---|
| `assets/7z.exe` | 7z archives |
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
| `Not a readable cpio image: …` | not a cpio — try opening an archive entry inside it, or load a backup |
| `Empty cpio image.` | truncated file; the backup picker opens automatically |
| `img-creater.exe could not pack this image` | the unpacked tree changed shape (missing `./` entries) — re-extract |
| Nothing happens after Apply | Apply stages the change; you must also commit it back to the live image |
| GUI exits immediately | no display available (`twrp.py --gui` needs a desktop session) |

See also: [Commands](commands.md) · [Open With Registry](open-with-registry.md) · [Flow](flow.md)
