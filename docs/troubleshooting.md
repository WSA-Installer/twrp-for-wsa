# Troubleshooting

Common issues and solutions for TWRP for WSA.

---

## Table of Contents

- [ADB Issues](#adb-issues)
- [TWRP Boot Issues](#twrp-boot-issues)
- [Injection Issues](#injection-issues)
- [Recovery Flag Issues](#recovery-flag-issues)
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

## Getting Help

1. Check [GitHub Issues](https://github.com/WSA-Installer/twrp-for-wsa/issues)
2. Open a new [Bug Report](https://github.com/WSA-Installer/twrp-for-wsa/issues/new)
3. Include output of `twrp.exe --status --debug`
4. Include your WSA version and Windows version
