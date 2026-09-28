# Windows Explorer "Open With" for `.img`

> Register `.img` files so Windows Explorer offers **Open with → WSA IMG
> Manager**, plus a classic right-click verb — without stealing the file's
> default handler from 7-Zip, WinRAR or anything else.

Added after `4.1.0`. Code: `twrp.py` (`register_img_handler()`,
`unregister_img_handler()`, `img_open_command()`), CLI flags
`--register-img` / `--unregister-img`.

---

## What gets written

Root key: `HKEY_LOCAL_MACHINE\Software\Classes`, falling back to
`HKEY_CURRENT_USER\Software\Classes` when HKLM is not writable (non-elevated
shell).

| # | Key | Value | Purpose |
|---|---|---|---|
| 1 | `.img\OpenWithProgids` | `wsa-installer.img` = *(empty, REG_NONE)* | makes the ProgID eligible for the **Open with** list |
| 2 | `wsa-installer.img` | `""` = `WSA IMG Manager` (REG_SZ) | ProgID display name |
| 3 | `wsa-installer.img\DefaultIcon` | `…\assets\icon.ico` | icon in Explorer / dialog |
| 4 | `wsa-installer.img\shell\open\command` | the command below | what "Open with" runs |
| 5 | `.img\shell\WsaInstallerImgManager` | `Open in WSA IMG Manager` | classic right-click verb |
| 6 | `.img\shell\WsaInstallerImgManager` `MUIVerb` | `Open in WSA IMG Manager` | localized verb text |
| 7 | `.img\shell\WsaInstallerImgManager` `Icon` | `…\assets\icon.ico` | verb icon |
| 8 | `.img\shell\WsaInstallerImgManager\command` | the command below | what the verb runs |

**Frozen (installed) builds only**, three extra keys:

| Key | Value |
|---|---|
| `Applications\Twrp.exe` | `WSA IMG Manager` |
| `Applications\Twrp.exe\shell\open\command` | the command below |
| `Applications\Twrp.exe\SupportedTypes` | `.img` = *(REG_NONE)* |

### The command

| Build | Command |
|---|---|
| Frozen (`Twrp.exe` next to the main exe) | `"…\Twrp.exe" --gui --path "%1"` |
| Frozen, `Twrp.exe` missing | `"<current exe>" --gui --path "%1"` |
| Source / dev | `"<venv>\pythonw.exe" "<repo>\twrp.py" --gui --path "%1"` |

`%1` is the selected file. `--gui` opens the [IMG Manager](img-manager.md).

---

## What is *never* touched

`.img`'s own **default value** (`Software\Classes\.img`) is not opened for write
and not modified. Your existing default handler keeps working — this is purely
additive (a `OpenWithProgids` entry plus a `shell` verb).

---

## Using it

1. Register:
   ```bash
   twrp.py --register-img
   ```
   or run the app once — `_register_apk_handler()` calls it automatically on
   every start (and `--register-apk` does too).
2. In Explorer, right-click any `.img`:
   * **Windows 10 / classic menu** → the verb *Open in WSA IMG Manager* appears
     directly in the context menu.
   * **Windows 11 modern menu** → use **Show more options** for the classic verb;
     the *Open with* submenu (driven by `OpenWithProgids`) appears in the modern
     menu.
3. Remove:
   ```bash
   twrp.py --unregister-img
   ```
   also called from `_unregister_apk_handler()` and `--unregister-apk`.

Both commands end with `SHChangeNotify(0x08000000, 0x1000, …)` so Explorer
refreshes without a restart.

---

## Verification

```bat
reg query "HKLM\Software\Classes\.img\OpenWithProgids" /v wsa-installer.img
reg query "HKLM\Software\Classes\wsa-installer.img\shell\open\command"
reg query "HKLM\Software\Classes\.img\shell\WsaInstallerImgManager\command"
reg query "HKLM\Software\Classes\.img" /ve
```

The first three must exist; the last one must still be **your** original handler
(7-Zip, WinRAR, …). After `--unregister-img` the first three must be gone.

The registration prints exactly what it did:

```
  [registered] WSA IMG Manager (.img Open with) [HKLM]
  command: "C:\Program Files\WSA Installer\Twrp.exe" --gui --path "%1"
```

`[HKCU]` in that line means HKLM was denied and the fallback was used.

---

## Unregister behaviour

`unregister_img_handler()` removes **exactly** the keys above, in dependency
order (children first), for *both* hives, and is idempotent — running it twice
reports `0 entrie(s) removed`.

`Applications\Twrp.exe` is only deleted when its default value still equals
`WSA IMG Manager` — so an unrelated application's registration of the same name
is left alone.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Verb missing in the Windows 11 menu | expected — open **Show more options**, or use the *Open with* submenu |
| `[error] registry write failed: [WinError 5]` | no write access to HKLM and the HKCU probe also failed; run elevated |
| `[skip] twrp entry point not found` | the helper could not locate `Twrp.exe` / `twrp.py` — reinstall or run from source |
| Command points at the wrong Python | dev registration stores the absolute path of the venv's `pythonw.exe`; re-register after moving the tree |
| Icon missing | `assets/icon.ico` was not present at registration time — register again |
| Want a different verb text | `IMG_VERB_TEXT` / `IMG_VERB_KEY` constants in `twrp.py`, then re-register |

See also: [IMG Manager](img-manager.md) · [CLI Reference](cli-reference.md)
