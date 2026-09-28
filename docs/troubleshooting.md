# Troubleshooting

Common issues and solutions for TWRP for WSA.

---

## Table of Contents

- [ADB Issues](#adb-issues)
- [TWRP Boot Issues](#twrp-boot-issues)
- [Injection Issues](#injection-issues)
- [Recovery Flag Issues](#recovery-flag-issues)
- [Admin Password Gate](#admin-password-gate)
- [System Apps & Boltware](#system-apps--boltware)
- [Boot Hook](#boot-hook)
- [IMG Manager & .img Open With](#img-manager--img-open-with)
- [Getting Help](#getting-help)

---

## ADB Issues

### ADB shows "device" instead of "recovery"

**Symptom:** After enabling TWRP, `adb devices` shows `device` instead of `recovery`.

**Cause:** TWRP recovery has not booted yet. The `recovery` status only appears when TWRP is actively running.

**Solution:**

1. Verify the flag is set: `twrp.exe --status`
2. Ensure `recovery_flag` shows `true`
3. If not enabled, run: `twrp.exe --enable-twrp`
4. Restart WSA: terminate from Windows Settings and relaunch, or run `adb reboot recovery`
5. TWRP recovery auto-starts on next boot — no need to enable Developer Mode or ADB Debugging for recovery detection

### ADB not connecting at all

**Symptom:** `adb devices` shows no devices.

**Solution:**

1. Restart ADB: `adb kill-server && adb start-server`
2. Connect manually: `adb connect 127.0.0.1:58526`
3. If connecting to TWRP recovery, ensure WSA is restarted after enabling TWRP mode
4. Enable **Developer Mode** and **ADB Debugging** in WSA Settings only if you need ADB access to Android (not required for TWRP recovery)

### ADB shows "unauthorized"

**Solution:**

1. Open WSA Settings -> Developer
2. Toggle ADB debugging off and on
3. Accept the authorization dialog

---

## TWRP Boot Issues

### TWRP not booting — goes straight to Android

**Solution:**

1. Check status: `twrp.exe --status`
2. If `TWRP Support` shows `false`, re-inject: `twrp.exe --inject twrp.7z`
3. Re-enable: `twrp.exe --enable-twrp`
4. Restart WSA completely

### TWRP boots but freezes

**Solution:**

1. Try ADB: `adb shell`
2. Use TWRP via command line: `adb shell twrp backup`
3. Restart WSA: `adb reboot`

---

## Injection Issues

### "initrd.img not found"

**Solution:**

1. Ensure WSA is installed
2. Check default path exists
3. Use `--path` for custom location: `twrp.exe --inject twrp.7z --path D:\initrd.img`

### "Permission denied"

**Solution:**

1. Run terminal as **administrator**
2. Stop WSA first: `taskkill /F /IM WsaClient.exe`
3. Retry the command

### Injection succeeds but TWRP not working

**Solution:**

1. Run with debug: `twrp.exe --inject twrp.7z --debug`
2. Check if patch.json is present in twrp.7z
3. Verify the initrd.img was modified: `twrp.exe --status`

---

## Recovery Flag Issues

### Flag not toggling

**Solution:**

1. Check the current flag: `twrp.exe --status`
2. Use `--path` to target the correct initrd.img
3. Run with `--debug` to see detailed output

### Flag reverts after WSA update

**Cause:** WSA updates replace the initrd.img.

**Solution:**

1. Re-inject after updates: `twrp.exe --inject twrp.7z`
2. Re-enable: `twrp.exe --enable-twrp`

---

## Admin Password Gate

### "Wrong password" on `--admin`

**Cause:** the SHA-256 of the typed password does not match
`ADMIN_PASSWORD_SHA256`; the gate allows **3 attempts**, then exits `1`
*without* opening any archive.

**Solution:**

1. Retry, or automate it in scripts:
   `set WSA_ADMIN_PASSWORD=<password>` then run the same `--admin` command
2. Remember `--admin` only matters for ADMIN-module operations — drop the flag
   to work in the USER module (no prompt at all)
3. Never paste the password into an issue; only the hash is in the source

### Command asks for a password when I did not expect it

Only these need `--admin`: `--install-as-system-app`, `--update-as-system-app`,
`--uninstall-boltware` (when the app lives in ADMIN) and `--repaire-magisk-hook`
against the ADMIN image. `--list-of-boltware`, `--status` and `--gui` never do.

---

## System Apps & Boltware

### `--list-of-boltware` prints nothing

**Cause:** the module image is missing — it is only created when something is
installed into it.

**Solution:**

1. Confirm with `twrp.exe --status` (both module lines are printed)
2. Install something: `twrp.exe --install-as-system-app app.apk`
3. Use `--path` if you are working on a detached image

### `--install-as-system-app` fails to identify the APK

**Cause:** `assets/aaptpp.exe` missing or blocked.

**Solution:** restore `assets/aaptpp.exe` next to `twrp.py`, or run from the
repository where it is bundled. Run with `--debug` for the full trace.

### Uninstall did nothing

**Solution:**

1. Removals are applied by the boot hook **on the next Android boot** — reboot
   first (`adb reboot`)
2. Check the hook is installed: `twrp.exe --install-magisk-hook`
3. Confirm the package is listed: `twrp.exe --list-of-boltware`

---

## Boot Hook

### `hook_issues()` reports problems

**Run:**

```cmd
twrp.exe --install-magisk-hook
```

If issues remain, force a clean rebuild from the payload:

```cmd
twrp.exe --repaire-magisk-hook        (needs --admin for the ADMIN image)
```

Typical findings: missing `overlay.d/sbin`, wrong mode on
`lspinit`/`magiskinit`/`wsainit`, or `post-fs-data.sh` without the
`# --- TWRP uninstall handler` marker.

### Hook keeps coming back after a WSA update

**Cause:** WSA updates replace `initrd.img`, which carries the hook with it.

**Solution:** re-inject, then re-install the hook — see
[Magisk Hook](magisk-hook.md).

---

## IMG Manager & .img Open With

### `--gui` will not start

**Solution:**

1. `pip install -r requirements.txt` (PySide6 6.5+)
2. Run from the repository root: `python twrp.py --gui`
3. Check the console traceback — a missing `assets/` folder is the usual cause

### A save failed — how do I get my image back?

Every save writes `initrd.img.bak-YYYYMMDD-HHMMSS` **before** touching the
file. Use the restore picker in the IMG Manager, or copy the `.bak` back by
hand. Details: [IMG Manager](img-manager.md#backups).

### `.img` files still open with another program

**Solution:**

1. `twrp.exe --register-img` — run a terminal **as administrator** if you want
   the HKLM (machine-wide) association; otherwise it falls back to HKCU
2. Unregister first if the entry is stale: `twrp.exe --unregister-img`
   (idempotent, safe to run twice)
3. Right-click → *Open with* → *Choose another app* → *WSA IMG Manager*

---

## Getting Help

1. Check [GitHub Issues](https://github.com/WSA-Installer/twrp-for-wsa/issues)
2. Open a new [Bug Report](https://github.com/WSA-Installer/twrp-for-wsa/issues/new)
3. Include output of `twrp.exe --status --debug`
4. Include your WSA version and Windows version
