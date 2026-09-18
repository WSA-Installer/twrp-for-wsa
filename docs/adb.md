# ADB Commands for TWRP

ADB (Android Debug Bridge) commands for working with TWRP recovery in WSA.

---

## Table of Contents

- [Connection](#connection)
- [TWRP-Specific Commands](#twrp-specific-commands)
- [File Operations](#file-operations)
- [Backup and Restore](#backup-and-restore)
- [System Operations](#system-operations)
- [Troubleshooting](#troubleshooting)

---

## Connection

### Default WSA ADB Port

WSA uses port **58526** for ADB connections:

```cmd
adb connect 127.0.0.1:58526
```

### Check Connection

```cmd
adb devices
```

**Expected output (Android mode):**
```
List of devices attached
127.0.0.1:58526    device
```

**Expected output (TWRP recovery mode):**
```
List of devices attached
127.0.0.1:58526    recovery
```

### Restart ADB Server

```cmd
adb kill-server
adb start-server
adb connect 127.0.0.1:58526
```

---

## TWRP-Specific Commands

### Enter TWRP Recovery

```cmd
adb reboot recovery
```

### Reboot to Android

```cmd
adb reboot
```

### Check TWRP Version

```cmd
adb shell twrp --version
```

### Open TWRP Shell

```cmd
adb shell
```

---

## File Operations

### Push File to WSA

```cmd
adb push local_file /sdcard/
adb push local_file /data/local/tmp/
```

### Pull File from WSA

```cmd
adb pull /sdcard/file.txt .
adb pull /data/local/tmp/file.txt C:\Downloads\
```

### List Files

```cmd
adb shell ls /sdcard/
adb shell ls /data/local/tmp/
```

### Create Directory

```cmd
adb shell mkdir /sdcard/backup
```

---

## Backup and Restore

### Full NANDroid Backup

```cmd
adb shell twrp backup
```

### Backup Specific Partition

```cmd
adb shell twrp backup boot
adb shell twrp backup system
adb shell twrp backup data
```

### Restore Backup

```cmd
adb shell twrp restore
```

### List Backups

```cmd
adb shell ls /sdcard/TWRP/BACKUPS/
```

---

## System Operations

### Mount Partition

```cmd
adb shell twrp mount /system
adb shell twrp mount /data
```

### Unmount Partition

```cmd
adb shell twrp unmount /system
adb shell twrp unmount /data
```

### Wipe Cache

```cmd
adb shell twrp wipe cache
```

### Wipe Dalvik Cache

```cmd
adb shell twrp wipe dalvik
```

### Factory Reset

```cmd
adb shell twrp wipe data
```

### Flash ZIP

```cmd
adb shell twrp install /sdcard/magisk.zip
adb push magisk.zip /sdcard/
adb shell twrp install /sdcard/magisk.zip
```

---

## System Operations

### Get Build Info

```cmd
adb shell getprop ro.build.display.id
adb shell getprop ro.build.version.release
```

### List Packages

```cmd
adb shell pm list packages
```

### Uninstall Package

```cmd
adb shell pm uninstall com.package.name
```

### Start Activity

```cmd
adb shell am start -n com.package.name/.ActivityName
```

### Run as Root

```cmd
adb root
```

---

## Troubleshooting

### ADB Device Not Found

```cmd
adb kill-server
adb start-server
adb connect 127.0.0.1:58526
adb devices
```

### ADB Unauthorized

1. Open WSA Settings → Developer
2. Toggle ADB debugging off and on
3. Accept the authorization dialog on screen

### Cannot Connect to Recovery

1. Verify TWRP is enabled: `twrp.exe --status`
2. Restart WSA after enabling TWRP
3. Try: `adb kill-server && adb start-server`
4. Connect: `adb connect 127.0.0.1:58526`

### ADB Shell Hangs

```cmd
adb reconnect
adb connect 127.0.0.1:58526
```

### File Transfer Fails

1. Ensure sufficient disk space
2. Check file permissions
3. Try a different location (`/data/local/tmp/`)

---

## Common ADB Commands Reference

| Command | Description |
|:--------|:------------|
| `adb devices` | List connected devices |
| `adb connect 127.0.0.1:58526` | Connect to WSA |
| `adb disconnect` | Disconnect from WSA |
| `adb reboot` | Reboot to Android |
| `adb reboot recovery` | Reboot to TWRP |
| `adb push <local> <remote>` | Push file to WSA |
| `adb pull <remote> <local>` | Pull file from WSA |
| `adb shell` | Open shell session |
| `adb install <apk>` | Install APK |
| `adb uninstall <package>` | Uninstall package |
| `adb root` | Restart ADB as root |
| `adb remount` | Remount system partition |
| `adb logcat` | View system logs |
