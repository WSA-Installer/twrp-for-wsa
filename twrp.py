#!/usr/bin/env python
"""
twrp.py -- TWRP Recovery For WSA v4.1.0
Permanent TWRP via initrd.img cpio patch.
Custom dispatcher boots TWRP or Android based on recovery_flag in info.json.
"""

from __future__ import annotations

import json
import sys
import os
import re
import subprocess
import time
import shutil
import socket
import ctypes
import argparse
import struct
import getpass
import winreg
import threading
import tempfile
import hashlib
import gzip
import lzma
import bz2
import io
import zipfile
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal, QObject, QEventLoop
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QTreeWidget, QTreeWidgetItem, QMenu, QFileDialog,
    QInputDialog, QMessageBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QHeaderView, QAbstractItemView, QSizeGrip, QDialog, QPlainTextEdit,
    QCheckBox, QLineEdit,
)


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            p = os.path.join(meipass, relative_path)
            if os.path.exists(p):
                return p
        exe_dir = os.path.dirname(sys.executable)
        p = os.path.join(exe_dir, relative_path)
        if os.path.exists(p):
            return p
        internal_path = os.path.join(exe_dir, "_internal", relative_path)
        if os.path.exists(internal_path):
            return internal_path
    local_base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(local_base, relative_path)


APP_NAME = "TWRP Recovery For WSA"
APP_VERSION = "4.1.0"


def _detect_cli_name():
    exe = os.path.basename(sys.executable).lower()
    if getattr(sys, 'frozen', False):
        return os.path.splitext(exe)[0]
    argv0 = sys.argv[0] if sys.argv else ""
    base = os.path.basename(argv0).lower()
    if base.endswith(".exe"):
        return os.path.splitext(base)[0]
    return "twrp.py"


CLI_NAME = _detect_cli_name()
WSA_PKG = "MicrosoftCorporationII.WindowsSubsystemForAndroid"
WSA_FAMILY = "MicrosoftCorporationII.WindowsSubsystemForAndroid_8wekyb3d8bbwe"
SEVEN_ZIP = resource_path(os.path.join("assets", "7z.exe"))
ADB_PATH = resource_path(os.path.join("assets", "adb.exe"))
ASSET_TWRP_7Z = resource_path(os.path.join("assets", "twrp.7z"))
ASSET_FIX_7Z = resource_path(os.path.join("assets", "fix.7z"))
AAPT_PP = resource_path(os.path.join("assets", "aaptpp.exe"))
IMG_CREATER = resource_path(os.path.join("assets", "img-creater.exe"))
IMG_EXTRACTOR = resource_path(os.path.join("assets", "img-checker.exe"))
LSP_IMAGE_NAME = "lsp_wsa-installer.img"
LSP_IMAGE_NAME_USER = "lsp_wsa-installer-user.img"
INJECT_TEMP = os.path.join(os.environ.get("TEMP", os.environ.get("TMP", tempfile.gettempdir())), "twrp_temp")
LSP_TEMP = os.path.join(INJECT_TEMP, "lsp_installer")
FIX_TEMP = os.path.join(INJECT_TEMP, "Initrd-fix")
ADB_PORT = 58526
ADB_HOST = "127.0.0.1"
ADB_DEVICE = f"{ADB_HOST}:{ADB_PORT}"
CREATE_NO_WINDOW = 0x08000000
DEBUG = False
LOG_FOR_USER = False

# --- admin / user module images -------------------------------------------
# Two independent LSP images live in the initrd. The boot hook
# (overlay.d/sbin/post-fs-data.sh) mounts EVERY file matching lsp_*.img and
# runs that image's own post-fs-data.sh, so both coexist without any shell
# change. Each image's own module.prop id decides which
# /data/adb/modules/<id> directory is created on boot.
ADMIN_PASSWORD_SHA256 = "fa882c068ae2288ce8cd32c14b00715c64a5494f1bbeff69e18ab8446452a6e9"
ADMIN_PASSWORD_ATTEMPTS = 3

IMAGE_SPECS = {
    "admin": {
        "image": LSP_IMAGE_NAME,
        "mod_id": "wsa-installer",
        "mod_name": "WSA Installer",
        "temp": "lsp_installer",
        "priv_xml": "privapp-permissions-wsa-installer.xml",
        "def_xml": "default-permissions-wsa-installer.xml",
        "label": "admin",
        "description": (
            "WSA Installer - admin module: system apps and boot hook for WSA. "
            "Reason: the admin installs this TWRP module into the WSA image so the "
            "preinstalled system apps (bloatware) that power native Windows-Android "
            "integration - Termux shell, WebDAV share, CLI bridge - plus the boot "
            "hook that applies scheduled changes, are always part of the system "
            "image; access is protected by the --admin password."
        ),
    },
    "user": {
        "image": LSP_IMAGE_NAME_USER,
        "mod_id": "wsa-installer-user",
        "mod_name": "WSA Installer (User)",
        "temp": "lsp_installer_user",
        "priv_xml": "privapp-permissions-wsa-installer-user.xml",
        "def_xml": "default-permissions-wsa-installer-user.xml",
        "label": "user",
        "description": (
            "WSA Installer (User) - user system apps for WSA. Reason: the same TWRP "
            "module system, but built and installed by the user for the system apps "
            "they choose to add as system apps; it lives in a separate image so "
            "those apps can be installed, updated or removed without touching the "
            "admin module and without any password."
        ),
    },
}

# Active-module globals (re-pointed by select_image()). Defaults = admin.
LSP_MOD_ID = IMAGE_SPECS["admin"]["mod_id"]
LSP_MOD_NAME = IMAGE_SPECS["admin"]["mod_name"]
LSP_PRIV_XML = IMAGE_SPECS["admin"]["priv_xml"]
LSP_DEF_XML = IMAGE_SPECS["admin"]["def_xml"]
LSP_LABEL = IMAGE_SPECS["admin"]["label"]
LSP_MOD_DESC = IMAGE_SPECS["admin"]["description"]


def image_spec(mode):
    """Spec dict for "admin" / "user". Anything else falls back to "user"."""
    if mode == "admin":
        return IMAGE_SPECS["admin"]
    return IMAGE_SPECS["user"]


def select_image(mode):
    """Point the module-level LSP_* globals at the chosen module image.

    Every LSP helper (has/extract/repack/find/create) reads those globals,
    so this one call is the single switch between admin and user module."""
    global LSP_IMAGE_NAME, LSP_TEMP, LSP_MOD_ID, LSP_MOD_NAME
    global LSP_PRIV_XML, LSP_DEF_XML, LSP_LABEL, LSP_MOD_DESC
    spec = image_spec(mode)
    LSP_IMAGE_NAME = spec["image"]
    LSP_TEMP = spec["temp"]
    LSP_MOD_ID = spec["mod_id"]
    LSP_MOD_NAME = spec["mod_name"]
    LSP_PRIV_XML = spec["priv_xml"]
    LSP_DEF_XML = spec["def_xml"]
    LSP_LABEL = spec["label"]
    LSP_MOD_DESC = spec["description"]
    return spec


def resolve_mode(mode, default="user"):
    """CLI mode resolution: None -> default, otherwise admin/user."""
    if mode in ("admin", "user"):
        return mode
    return default


def _require_admin_password():
    """--admin gate. True only when the entered password hashes to
    ADMIN_PASSWORD_SHA256. The plaintext never touches the source tree."""
    expected = ADMIN_PASSWORD_SHA256
    env = os.environ.get("WSA_ADMIN_PASSWORD", "")
    if env:
        if hashlib.sha256(env.encode("utf-8")).hexdigest() == expected:
            print("  Password accepted (WSA_ADMIN_PASSWORD).", flush=True)
            return True
        print("  WSA_ADMIN_PASSWORD does not match - falling back to prompt.", flush=True)
    for attempt in range(1, ADMIN_PASSWORD_ATTEMPTS + 1):
        try:
            entered = getpass.getpass("Enter the password: ")
        except (EOFError, KeyboardInterrupt):
            print("\n  Password required for --admin. Aborted.", flush=True)
            return False
        if hashlib.sha256(entered.encode("utf-8")).hexdigest() == expected:
            print("  Password accepted. Admin module access granted.", flush=True)
            return True
        print(f"  Wrong password ({attempt}/{ADMIN_PASSWORD_ATTEMPTS}).", flush=True)
    print("  Too many failed attempts - admin install cancelled.", flush=True)
    return False


# --- .img "Open with" / Explorer context menu -------------------------------
IMG_PROGID = "wsa-installer.img"
IMG_VERB_KEY = "WsaInstallerImgManager"
IMG_VERB_TEXT = "Open in WSA IMG Manager"
IMG_DESC = "WSA IMG Manager"


def _img_icon_path():
    _dir = os.path.dirname(os.path.abspath(__file__))
    for name in ("icon.ico", "twrp.ico"):
        p = os.path.join(_dir, "assets", name)
        if os.path.isfile(p):
            return p
    return os.path.abspath(sys.executable)


def img_open_command(command=None):
    """Registry command line that opens an .img with the IMG Manager GUI."""
    if command:
        return command
    _here = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False):
        _exe = os.path.dirname(os.path.abspath(sys.executable))
        _twrp = os.path.join(_exe, "Twrp.exe")
        if os.path.isfile(_twrp):
            return f'"{_twrp}" --gui --path "%1"'
        return f'"{os.path.abspath(sys.executable)}" --gui --path "%1"'
    _script = os.path.join(_here, "twrp.py")
    _pyw = os.path.join(_here, "venv", "Scripts", "pythonw.exe")
    if not os.path.isfile(_pyw):
        _pyw = sys.executable
    return f'"{_pyw}" "{_script}" --gui --path "%1"'


def register_img_handler(command=None):
    """Add ".img -> Open with -> WSA IMG Manager" plus a classic right-click verb.

    Only additive keys are written: .img's own default value is never touched,
    so the existing default handler (7-Zip, WinRAR, ...) keeps working."""
    cmd = img_open_command(command)
    icon = _img_icon_path()
    cls = "Software\\Classes"

    hk = winreg.HKEY_LOCAL_MACHINE
    root_name = "HKLM"
    try:
        _probe = winreg.OpenKey(hk, f"{cls}\\.img", 0, winreg.KEY_WRITE)
        winreg.CloseKey(_probe)
    except OSError:
        hk = winreg.HKEY_CURRENT_USER
        root_name = "HKCU"

    writes = [
        # 1) makes the ProgID eligible for the "Open with" list
        (f"{cls}\\.img\\OpenWithProgids", IMG_PROGID, b"", winreg.REG_NONE),
        # 2) the named ProgID entry
        (f"{cls}\\{IMG_PROGID}", "", IMG_DESC, winreg.REG_SZ),
        (f"{cls}\\{IMG_PROGID}\\DefaultIcon", "", icon, winreg.REG_SZ),
        (f"{cls}\\{IMG_PROGID}\\shell\\open\\command", "", cmd, winreg.REG_SZ),
        # 3) classic right-click verb directly on the extension
        (f"{cls}\\.img\\shell\\{IMG_VERB_KEY}", "", IMG_VERB_TEXT, winreg.REG_SZ),
        (f"{cls}\\.img\\shell\\{IMG_VERB_KEY}", "MUIVerb", IMG_VERB_TEXT, winreg.REG_SZ),
        (f"{cls}\\.img\\shell\\{IMG_VERB_KEY}", "Icon", icon, winreg.REG_SZ),
        (f"{cls}\\.img\\shell\\{IMG_VERB_KEY}\\command", "", cmd, winreg.REG_SZ),
    ]
    # 4) exe-based Open-with entry (frozen build only)
    if getattr(sys, "frozen", False):
        writes += [
            (f"{cls}\\Applications\\Twrp.exe", "", IMG_DESC, winreg.REG_SZ),
            (f"{cls}\\Applications\\Twrp.exe\\shell\\open\\command", "", cmd, winreg.REG_SZ),
            (f"{cls}\\Applications\\Twrp.exe\\SupportedTypes", ".img", b"", winreg.REG_NONE),
        ]

    try:
        for path, name, value, kind in writes:
            with winreg.CreateKey(hk, path) as k:
                winreg.SetValueEx(k, name, 0, kind, value)
    except OSError as ex:
        print(f"  [error] registry write failed: {ex}", flush=True)
        return 1

    print(f"  [registered] {IMG_DESC} (.img Open with) [{root_name}]", flush=True)
    print(f"  command: {cmd}", flush=True)
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x1000, None, None)
    except Exception:
        pass
    return 0


def unregister_img_handler():
    """Remove exactly the keys register_img_handler() wrote (idempotent)."""
    cls = "Software\\Classes"
    removed = 0

    def _del_value(hive, path, name):
        nonlocal removed
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
                removed += 1
        except OSError:
            pass

    def _del_key(hive, path):
        nonlocal removed
        try:
            winreg.DeleteKey(hive, path)
            removed += 1
        except OSError:
            pass

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        _del_value(hive, f"{cls}\\.img\\OpenWithProgids", IMG_PROGID)
        for p in (
            f"{cls}\\.img\\shell\\{IMG_VERB_KEY}\\command",
            f"{cls}\\.img\\shell\\{IMG_VERB_KEY}",
            f"{cls}\\{IMG_PROGID}\\shell\\open\\command",
            f"{cls}\\{IMG_PROGID}\\shell\\open",
            f"{cls}\\{IMG_PROGID}\\shell",
            f"{cls}\\{IMG_PROGID}\\DefaultIcon",
            f"{cls}\\{IMG_PROGID}",
        ):
            _del_key(hive, p)
        _del_value(hive, f"{cls}\\Applications\\Twrp.exe\\SupportedTypes", ".img")
        for p in (
            f"{cls}\\Applications\\Twrp.exe\\shell\\open\\command",
            f"{cls}\\Applications\\Twrp.exe\\shell\\open",
            f"{cls}\\Applications\\Twrp.exe\\shell",
        ):
            _del_key(hive, p)
        # only remove the Applications\Twrp.exe key if we own it
        try:
            with winreg.OpenKey(hive, f"{cls}\\Applications\\Twrp.exe") as k:
                _v, _t = winreg.QueryValueEx(k, "")
            if _v == IMG_DESC:
                _del_key(hive, f"{cls}\\Applications\\Twrp.exe\\SupportedTypes")
                _del_key(hive, f"{cls}\\Applications\\Twrp.exe")
        except OSError:
            pass

    print(f"  [unregistered] {IMG_DESC} (.img Open with) - {removed} entrie(s) removed",
          flush=True)
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x1000, None, None)
    except Exception:
        pass
    return 0


POSTFSDATA_ARCNAME = "overlay.d/sbin/post-fs-data.sh"
POSTFSDATA_MARKER = b"# --- TWRP uninstall handler"
SHELLCHECK_LINE = b"    # shellcheck disable=SC2174\n"
HOOK_MODES = {
    "lspinit": 0o100750,
    "magiskinit": 0o100750,
    "wsainit": 0o100777,
    POSTFSDATA_ARCNAME: 0o100644,
}
HOOK_DIRS = ["overlay.d", "overlay.d/sbin"]
HOOK_DIR_MODE = 0o040750
EXEC_NAMES = {
    "init", "init.real", "recovery", "twrp", "adbd", "sh", "busybox",
    "magiskinit", "magisk", "magisk32", "magisk64", "supolicy", "ksud",
    "lspinit", "wsainit", "su", "setprop", "getprop", "start",
}
TWRP_REQUIRED_FILES = ("/sbin/twrp", "/sbin/busybox", "/sbin/linker64", "/info.json")
TWRP_REQUIRED_DIRS = ("/twres", "/etc", "/system/lib64")
# twrp_support key inside info.json; value may be "True"/"true"/true/...
TWRP_FLAG_RE = re.compile(
    br'("twrp_support"\s*:\s*)("[^"]*"|true|false)', re.IGNORECASE)
# same treatment for recovery_flag (byte patterns cover the shipped layout
# only when the spacing matches exactly, hence the fallback)
RECOVERY_FLAG_RE = re.compile(
    br'("recovery_flag"\s*:\s*)("[^"]*"|true|false)', re.IGNORECASE)
POSTFSDATA_UNINSTALL_BLOCK = (
    b"\n# --- TWRP uninstall handler (background) ---\n"
    b"(\n"
    b"    while [ \"$(getprop sys.boot_completed)\" != \"1\" ]; do sleep 1; done\n"
    b"    sleep 5\n"
    b"    mkdir -p /storage/emulated/0/MT2\n"
    b"    EARLY_LOG=\"$(dirname \"$0\")/post-fs-data.log\"\n"
    b"    USER_LOG=\"/storage/emulated/0/MT2/uninstall.log\"\n"
    b"    cp -f \"$EARLY_LOG\" \"$USER_LOG\" 2>/dev/null\n"
    b"    log_uninstall() {\n"
    b"        echo \"[$(date '+%Y-%m-%d %H:%M:%S')] $1\" >> \"$EARLY_LOG\"\n"
    b"        echo \"[$(date '+%Y-%m-%d %H:%M:%S')] $1\" >> \"$USER_LOG\"\n"
    b"    }\n"
    b"    UNINSTALL_FILE=\"$(dirname \"$0\")/uninstall.txt\"\n"
    b"    if [ -f \"$UNINSTALL_FILE\" ]; then\n"
    b"        log_uninstall \"=== TWRP Uninstall start ===\"\n"
    b"        while IFS= read -r PKG; do\n"
    b"            [ -z \"$PKG\" ] && continue\n"
    b"            log_uninstall \"UNINSTALL: $PKG\"\n"
    b"            if pm uninstall \"$PKG\" 2>/dev/null; then\n"
    b"                log_uninstall \"  UNINSTALLED: $PKG\"\n"
    b"            else\n"
    b"                log_uninstall \"  FAILED: $PKG\"\n"
    b"            fi\n"
    b"        done < \"$UNINSTALL_FILE\"\n"
    b"        rm -f \"$UNINSTALL_FILE\"\n"
    b"        log_uninstall \"=== TWRP Uninstall complete ===\"\n"
    b"    fi\n"
    b") &\n"
    b"# --- end TWRP uninstall handler ---\n"
)


def guess_mode(arcname, data):
    base = arcname.rstrip("/").split("/")[-1].lower()
    if arcname in HOOK_MODES:
        return HOOK_MODES[arcname]
    if base.endswith(".sh"):
        return 0o100755
    if base in EXEC_NAMES:
        return 0o100755
    if isinstance(data, (bytes, bytearray)) and data[:4] == b"\x7fELF":
        if ".so" not in base:
            return 0o100755
    return 0o100644


def _looks_like_text(data):
    """True when `data` decodes cleanly as UTF-8, i.e. the editor can take it."""
    if not data:
        return True
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _walk_dir(src_dir):
    """(arcname, is_dir, full_path) under src_dir, directories first and
    depth-ascending so archives built from it keep a valid entry order.

    A symlink to a folder is reported as a FILE row: os.walk does not descend
    into it (followlinks=False) and the link itself must be written back as a
    link, not as a directory it does not contain.
    """
    rows = []
    for dirpath, dirnames, filenames in os.walk(src_dir):
        rel = os.path.relpath(dirpath, src_dir).replace("\\", "/")
        rel = "" if rel == "." else rel
        for name in dirnames:
            full = os.path.join(dirpath, name)
            try:
                linked = os.path.islink(full)
            except OSError:
                linked = False
            rows.append((f"{rel}/{name}" if rel else name, not linked, full))
        for name in filenames:
            rows.append((f"{rel}/{name}" if rel else name, False,
                         os.path.join(dirpath, name)))
    rows.sort(key=lambda row: (0 if row[1] else 1,
                               row[0].count("/"), row[0].lower()))
    return rows


def _read_link_target(full):
    """Symlink target, whether the OS gave us a real link or a plain file."""
    try:
        if os.path.islink(full):
            return os.readlink(full)
    except OSError:
        pass
    try:
        with open(full, "rb") as handle:
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _symlink_target(full, arcname, orig_modes):
    """Link target when this row must be written as a symlink, else None.

    Checks both the recorded cpio mode and the filesystem, so a link the user
    just added in the editor is not mistaken for a regular file (opening a
    Windows link can fail outright).
    """
    mode = orig_modes.get(arcname)
    is_link = mode is not None and (mode & 0o170000) == 0o120000
    try:
        if os.path.islink(full):
            is_link = True
    except OSError:
        pass
    return _read_link_target(full) if is_link else None


def _file_perms(arcname, data, orig_modes):
    """Permission bits: keep the original when we have one, else guess."""
    mode = orig_modes.get(arcname)
    if mode is not None and (mode & 0o7777):
        return mode & 0o7777
    return guess_mode(arcname, data) & 0o7777


def build_cpio_from_dir(src_dir, orig_modes=None):
    """Rebuild a cpio archive from an edited tree, entirely in memory.

    Symlinks round-trip through _read_link_target(); every entry the user did
    not touch keeps its original mode.
    """
    orig_modes = orig_modes or {}
    parts = []
    for arcname, is_dir, full in _walk_dir(src_dir):
        mode = orig_modes.get(arcname)
        if is_dir:
            if mode is not None and (mode & 0o170000) == 0o040000:
                perms = mode & 0o7777
            else:
                perms = 0o0755
            parts.append(CpioUtils._build_entry(arcname, b"",
                                                mode=0o040000 | perms))
            continue
        target = _symlink_target(full, arcname, orig_modes)
        if target is not None:
            parts.append(CpioUtils._build_entry(
                arcname, target.encode("utf-8"), mode=0o120777))
            continue
        with open(full, "rb") as handle:
            data = handle.read()
        parts.append(CpioUtils._build_entry(
            arcname, data, mode=0o100000 | _file_perms(arcname, data, orig_modes)))
    parts.append(CpioUtils._trailer_entry())
    return b"".join(parts)


def build_zip_from_dir(src_dir, orig_modes=None):
    """Rebuild a zip archive from an edited tree."""
    orig_modes = orig_modes or {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, is_dir, full in _walk_dir(src_dir):
            mode = orig_modes.get(arcname)
            info = zipfile.ZipInfo(arcname + "/" if is_dir else arcname)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            if is_dir:
                if mode is not None and (mode & 0o170000) == 0o040000:
                    info.external_attr = ((0o040000 | (mode & 0o7777)) << 16)
                else:
                    info.external_attr = (0o040755 << 16) | 0x10
                zf.writestr(info, b"")
                continue
            target = _symlink_target(full, arcname, orig_modes)
            if target is not None:
                info.external_attr = 0o120777 << 16
                zf.writestr(info, target.encode("utf-8"))
                continue
            with open(full, "rb") as handle:
                data = handle.read()
            perms = _file_perms(arcname, data, orig_modes)
            info.external_attr = (0o100000 | perms) << 16
            zf.writestr(info, data)
    return buffer.getvalue()


def build_tar_from_dir(src_dir, orig_modes=None):
    """Rebuild an uncompressed tar archive from an edited tree."""
    orig_modes = orig_modes or {}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tf:
        for arcname, is_dir, full in _walk_dir(src_dir):
            mode = orig_modes.get(arcname)
            info = tarfile.TarInfo(arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            if is_dir:
                info.type = tarfile.DIRTYPE
                if mode is not None and (mode & 0o170000) == 0o040000:
                    info.mode = mode & 0o7777
                else:
                    info.mode = 0o0755
                tf.addfile(info)
                continue
            target = _symlink_target(full, arcname, orig_modes)
            if target is not None:
                info.type = tarfile.SYMTYPE
                info.mode = 0o0777
                info.linkname = target
                tf.addfile(info)
                continue
            with open(full, "rb") as handle:
                data = handle.read()
            info.type = tarfile.REGTYPE
            info.size = len(data)
            info.mode = _file_perms(arcname, data, orig_modes)
            tf.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def patch_postfsdata(base):
    out = base.replace(SHELLCHECK_LINE, b"")
    if POSTFSDATA_MARKER in out:
        return out
    return out + POSTFSDATA_UNINSTALL_BLOCK


DANGEROUS_PERMS = [
    "android.permission.READ_CALENDAR", "android.permission.WRITE_CALENDAR",
    "android.permission.CAMERA",
    "android.permission.READ_CONTACTS", "android.permission.WRITE_CONTACTS",
    "android.permission.GET_ACCOUNTS",
    "android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION", "android.permission.ACCESS_MEDIA_LOCATION",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_PHONE_STATE", "android.permission.READ_PHONE_NUMBERS",
    "android.permission.CALL_PHONE", "android.permission.ANSWER_PHONE_CALLS",
    "android.permission.PROCESS_OUTGOING_CALLS", "android.permission.ACCEPT_HANDOVER",
    "android.permission.READ_CALL_LOG", "android.permission.WRITE_CALL_LOG",
    "android.permission.ADD_VOICEMAIL", "android.permission.USE_SIP",
    "android.permission.BODY_SENSORS", "android.permission.BODY_SENSORS_BACKGROUND",
    "android.permission.ACTIVITY_RECOGNITION",
    "android.permission.SEND_SMS", "android.permission.RECEIVE_SMS",
    "android.permission.READ_SMS", "android.permission.RECEIVE_MMS",
    "android.permission.RECEIVE_WAP_PUSH",
    "android.permission.READ_EXTERNAL_STORAGE", "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.READ_MEDIA_IMAGES", "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO", "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
    "android.permission.BLUETOOTH_SCAN", "android.permission.BLUETOOTH_ADVERTISE",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.NEARBY_WIFI_DEVICES", "android.permission.UWB_RANGING",
    "android.permission.POST_NOTIFICATIONS",
]

SPECIAL_PERMS = [
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.WRITE_SETTINGS",
    "android.permission.REQUEST_INSTALL_PACKAGES",
    "android.permission.REQUEST_DELETE_PACKAGES",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.MANAGE_MEDIA",
    "android.permission.PACKAGE_USAGE_STATS",
    "android.permission.LOADER_USAGE_STATS",
    "android.permission.SCHEDULE_EXACT_ALARM",
    "android.permission.USE_FULL_SCREEN_INTENT",
    "android.permission.TURN_SCREEN_ON",
    "android.permission.INTERACT_ACROSS_PROFILES",
    "android.permission.INSTANT_APP_FOREGROUND_SERVICE",
    "android.permission.SMS_FINANCIAL_TRANSACTIONS",
    "android.permission.MANAGE_ONGOING_CALLS",
    "android.permission.MEDIA_ROUTING_CONTROL",
]

PRIVILEGED_PERMS = {
    "android.permission.WRITE_SECURE_SETTINGS", "android.permission.READ_LOGS",
    "android.permission.DUMP", "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.PACKAGE_USAGE_STATS", "android.permission.INTERACT_ACROSS_USERS",
    "android.permission.MANAGE_USERS", "android.permission.MASTER_CLEAR",
    "android.permission.REBOOT", "android.permission.STATUS_BAR",
    "android.permission.START_ACTIVITIES_FROM_BACKGROUND",
    "android.permission.INSTALL_PACKAGES", "android.permission.DELETE_PACKAGES",
    "android.permission.CLEAR_APP_USER_DATA",
    "android.permission.READ_PRIVILEGED_PHONE_STATE",
    "android.permission.CALL_PRIVILEGED", "android.permission.SET_TIME",
    "android.permission.SET_TIME_ZONE", "android.permission.SHUTDOWN",
    "android.permission.READ_DREAM_STATE",
    "android.permission.CHANGE_COMPONENT_ENABLED_STATE",
    "android.permission.CONNECTIVITY_INTERNAL", "android.permission.BACKUP",
    "android.permission.RECOVERY", "android.permission.UPDATE_DEVICE_STATS",
    "android.permission.WRITE_GSERVICES",
    "android.permission.RECEIVE_DATA_ACTIVITY_CHANGE",
    "android.permission.INVOKE_CARRIER_SETUP",
    "android.permission.PERFORM_CDMA_PROVISIONING",
    "android.permission.REQUEST_NETWORK_SCORES",
    "android.permission.OVERRIDE_WIFI_CONFIG",
    "android.permission.WRITE_APN_SETTINGS",
    "android.permission.NOTIFICATION_DURING_SETUP",
    "android.permission.LOCAL_MAC_ADDRESS",
    "android.permission.MANAGE_DEVICE_ADMINS",
    "android.permission.MANAGE_FINGERPRINT", "android.permission.MANAGE_USB",
    "android.permission.MODIFY_DAY_NIGHT_MODE",
    "android.permission.MODIFY_PHONE_STATE",
    "android.permission.READ_WIFI_CREDENTIAL",
    "android.permission.SUBSTITUTE_NOTIFICATION_APP_NAME",
    "android.permission.DISPATCH_PROVISIONING_MESSAGE",
    "android.permission.UPDATE_LOCK",
    "android.permission.MOUNT_UNMOUNT_FILESYSTEMS",
    "android.permission.ACCESS_FM_RADIO", "android.permission.BROADCAST_PHONE_INTENT",
    "android.permission.PERFORM_SMS_AUTH",
}

NORMAL_PERMS = [
    "android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.ACCESS_WIFI_STATE", "android.permission.CHANGE_NETWORK_STATE",
    "android.permission.CHANGE_WIFI_STATE", "android.permission.CHANGE_WIFI_MULTICAST_STATE",
    "android.permission.VIBRATE", "android.permission.WAKE_LOCK",
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK",
    "android.permission.FOREGROUND_SERVICE_LOCATION",
    "android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE",
    "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
    "android.permission.FOREGROUND_SERVICE_HEALTH",
    "android.permission.FOREGROUND_SERVICE_REMOTE_MESSAGING",
    "android.permission.FOREGROUND_SERVICE_SYSTEM_EXEMPTED",
    "android.permission.FOREGROUND_SERVICE_SHORT_SERVICE",
    "android.permission.RECEIVE_BOOT_COMPLETED",
    "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS",
    "android.permission.EXPAND_STATUS_BAR", "android.permission.DISABLE_KEYGUARD",
    "android.permission.SET_WALLPAPER", "android.permission.SET_WALLPAPER_HINTS",
    "android.permission.READ_SYNC_SETTINGS", "android.permission.WRITE_SYNC_SETTINGS",
    "android.permission.READ_SYNC_STATS", "android.permission.BLUETOOTH",
    "android.permission.BLUETOOTH_ADMIN", "android.permission.BLUETOOTH_PRIVILEGED",
    "android.permission.NFC", "android.permission.NFC_TRANSACTION_EVENT",
    "android.permission.NFC_HOST_CARD_EMULATION", "android.permission.ACCESS_BLUETOOTH_SHARE",
    "android.permission.SUBSCRIBE_TO_KEYGUARD_LOCKED", "android.permission.USE_BIOMETRIC",
    "android.permission.USE_FINGERPRINT", "android.permission.BIND_ACCESSIBILITY_SERVICE",
    "android.permission.ACCESS_NOTIFICATION_POLICY",
    "android.permission.ACCESS_NOTIFICATION_SERVICE", "android.permission.GET_TASKS",
    "android.permission.REAL_GET_TASKS", "android.permission.READ_APP_BADGE",
    "android.permission.WRITE_APP_BADGE", "com.android.launcher.permission.INSTALL_SHORTCUT",
    "com.android.launcher.permission.UNINSTALL_SHORTCUT",
    "android.permission.READ_DEVICE_CONFIG", "android.permission.WRITE_DEVICE_CONFIG",
    "android.permission.QUICK_SETTINGS_TILE", "com.android.alarm.permission.SET_ALARM",
    "android.permission.FLASHLIGHT", "android.permission.READ_HISTORY_BOOKMARKS",
    "android.permission.WRITE_HISTORY_BOOKMARKS", "android.permission.WRITE_MEDIA_STORAGE",
    "android.permission.READ_MEDIA_STORAGE", "android.permission.MANAGE_DOCUMENTS",
    "android.permission.MANAGE_SCOPED_STORAGE", "android.permission.CAPTURE_AUDIO_OUTPUT",
    "android.permission.CAPTURE_VIDEO_OUTPUT",
    "android.permission.CAPTURE_SECURE_VIDEO_OUTPUT",
    "android.permission.CAPTURE_TUNNEL_BUFFERS", "android.permission.FACTORY_RESET",
    "android.permission.SET_POINTER_SPEED", "android.permission.SET_KEYBOARD_LAYOUT",
    "android.permission.READ_FRAME_BUFFER", "android.permission.WRITE_FRAME_BUFFER",
    "android.permission.MAGNIFY_CONTROL", "android.permission.ACCESS_SURFACE_FLINGER",
    "android.permission.READ_INPUT_STATE", "android.permission.REORDER_TASKS",
    "android.permission.CHANGE_CONFIGURATION", "android.permission.KILL_BACKGROUND_PROCESSES",
    "android.permission.FORCE_STOP_PACKAGES", "android.permission.GET_APP_OPS_STATS",
    "android.permission.SET_ACTIVITY_WATCHER", "android.permission.SUSPEND_APPS",
    "android.permission.GET_TOP_ACTIVITY_INFO", "android.permission.SET_PROCESS_LIMIT",
    "android.permission.SET_ALWAYS_FINISH", "android.permission.SET_DEBUG_APP",
    "android.permission.MOVE_PACKAGE", "android.permission.ACCESS_ALL_EXTERNAL_STORAGE",
    "android.permission.MOUNT_FORMAT_FILESYSTEMS", "android.permission.STORAGE_INTERNAL",
    "android.permission.GLOBAL_SEARCH", "android.permission.MANAGE_ACCOUNTS",
    "android.permission.AUTHENTICATE_ACCOUNTS", "android.permission.USE_CREDENTIALS",
    "android.permission.INTERACT_ACROSS_USERS_FULL", "android.permission.CREATE_USERS",
    "android.permission.UPDATE_APP_OPS_STATS", "android.permission.ACCESS_KEYGUARD_SECURE",
    "android.permission.BIND_APPWIDGET", "android.permission.BIND_DEVICE_ADMIN",
    "android.permission.READ_PROFILE", "android.permission.WRITE_PROFILE",
    "android.permission.READ_SOCIAL_STREAM", "android.permission.WRITE_SOCIAL_STREAM",
    "android.permission.READ_USER_DICTIONARY", "android.permission.WRITE_USER_DICTIONARY",
    "android.permission.BIND_WALLPAPER", "android.permission.INSTALL_LOCATION_PROVIDER",
    "android.permission.INTERNAL_SYSTEM_WINDOW", "android.permission.LOCATION_HARDWARE",
    "android.permission.MANAGE_APEX_SERVICES", "android.permission.MANAGE_APP_TOKENS",
    "android.permission.MANAGE_CONTENT_CAPTURE",
    "android.permission.MANAGE_CONTENT_SUGGESTIONS",
    "android.permission.MANAGE_NOTIFIFICATION_POLICY",
    "android.permission.MANAGE_NOTIFICATION_LISTENERS", "android.permission.MANAGE_OWN_CALLS",
    "android.permission.MANAGE_ROLE_HOLDERS", "android.permission.MANAGE_SENSORS",
    "android.permission.MANAGE_VOICE_INTERACTION", "android.permission.MODIFY_AUDIO_ROUTING",
    "android.permission.NETWORK_SETUP_WIZARD", "android.permission.NOTIFICATION_LISTEN",
    "android.permission.OBSERVE_GRANT_REVOKE_PERMISSIONS",
    "android.permission.OBSERVE_APP_BIND", "android.permission.READ_INSTALL_SESSIONS",
    "android.permission.READ_NETWORK_USAGE_HISTORY",
    "android.permission.READ_WALLPAPER_INTERNAL",
    "android.permission.RECEIVE_EMERGENCY_BROADCAST", "android.permission.REMOVE_TASKS",
    "android.permission.REQUEST_PASSWORD_COMPLEXITY",
    "android.permission.RESET_FINGERPRINT_LOCKOUT", "android.permission.RESTART_PACKAGES",
    "android.permission.SEND_RESPOND_VIA_MESSAGE", "android.permission.SERIAL_PORT",
    "android.permission.SET_ANIMATION_SCALE", "android.permission.SET_INPUT_METHOD",
    "android.permission.SET_ORIENTATION", "android.permission.SET_PREFERRED_NETWORKS",
    "android.permission.START_TASKS_FROM_RECENTS", "android.permission.STOP_APP_SWITCHES",
    "android.permission.TRANSMIT_IR", "android.permission.UNINSTALL_SHORTCUT",
]


def _debug(msg):
    if DEBUG:
        print(f"  [DEBUG] {msg}", flush=True)


def _log(msg):
    print(f"  [INFO] {msg}", flush=True)


BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "wsa_twrp_logo.png"

REFERENCE_WIDTH = 2000
REFERENCE_HEIGHT = 1124
WINDOW_WIDTH =  603
WINDOW_HEIGHT = 337
HEADER_HEIGHT = 100
WINDOW_RADIUS = 30
BORDER_WIDTH = 3
ICON_RECT = QRectF(29, 18, 60, 60)
TITLE_RECT = QRectF(123, 25, 430, 52)
CLOSE_CENTER = QPoint(1950, 47)
CLOSE_HALF = 16
LOGO_RECT = QRectF(854, 417, 292, 287)
HEADER_COLOR = QColor(32, 32, 32)
MAIN_COLOR = QColor(0, 0, 0)
BORDER_COLOR = QColor(47, 47, 47)
TITLE_COLOR = QColor(245, 245, 245)
TEXT_COLOR = QColor(245, 245, 245)
PROGRESS_TRACK = QColor(206, 206, 206)
PROGRESS_FILL = QColor(169, 81, 192)
TITLE_FONT_SIZE = 32


class CpioUtils:
    MAGIC = b"070701"
    HEADER_SIZE = 110
    TRAILER_NAME = b"TRAILER!!!\x00"
    FLAG_TRUE = (b'"recovery_flag": "true" ', b'"recovery_flag": "True" ')
    FLAG_FALSE = (b'"recovery_flag": "false"', b'"recovery_flag": "False"')

    @staticmethod
    def _build_entry(name, data, mode=0o100644, uid=0, gid=0, nlink=1, mtime=0):
        if isinstance(name, str):
            name = name.encode("utf-8")
        if not name.endswith(b"\x00"):
            name += b"\x00"
        namesize = len(name)
        filesize = len(data)
        header = (
            CpioUtils.MAGIC
            + f"{0:08x}".encode()
            + f"{mode:08x}".encode()
            + f"{uid:08x}".encode()
            + f"{gid:08x}".encode()
            + f"{nlink:08x}".encode()
            + f"{mtime:08x}".encode()
            + f"{filesize:08x}".encode()
            + b"00000000"
            + b"00000000"
            + b"00000000"
            + b"00000000"
            + f"{namesize:08x}".encode()
            + b"00000000"
        )
        pad1 = (4 - ((len(header) + namesize) % 4)) % 4
        pad2 = (4 - (filesize % 4)) % 4
        return header + name + (b"\x00" * pad1) + data + (b"\x00" * pad2)

    @staticmethod
    def _trailer_entry():
        return CpioUtils._build_entry(b"TRAILER!!!", b"", mode=0, nlink=0)

    @staticmethod
    def _parse_header(header):
        if len(header) < 110 or header[:6] != b"070701":
            return None
        namesize = int(header[94:102], 16)
        filesize = int(header[54:62], 16)
        mode = int(header[14:22], 16)
        return {"namesize": namesize, "filesize": filesize, "mode": mode}

    @staticmethod
    def scan_entries(archive_path):
        _debug(f"scan_entries({os.path.basename(archive_path)})")
        entries = []
        with open(archive_path, "rb") as f:
            while True:
                pos = f.tell()
                header = f.read(110)
                fields = CpioUtils._parse_header(header)
                if fields is None:
                    break
                raw_name = f.read(fields["namesize"])
                if raw_name.rstrip(b"\x00") == CpioUtils.TRAILER_NAME.rstrip(b"\x00"):
                    break
                name = raw_name.rstrip(b"\x00").decode("utf-8", errors="replace")
                data_start = f.tell()
                pad = (4 - (data_start % 4)) % 4
                data_start += pad
                entries.append((name, data_start, fields["filesize"], pos))
                f.seek(data_start + fields["filesize"])
                pad2 = (4 - (fields["filesize"] % 4)) % 4
                if pad2:
                    f.read(pad2)
        _debug(f"scan_entries: found {len(entries)} entries")
        for name, ds, sz, hp in entries:
            _debug(f"  {name} ({sz:,} bytes)")
        return entries

    @staticmethod
    def read_file(archive_path, entry_name):
        _debug(f"read_file({os.path.basename(archive_path)}, {entry_name})")
        with open(archive_path, "rb") as f:
            while True:
                pos = f.tell()
                header = f.read(110)
                fields = CpioUtils._parse_header(header)
                if fields is None:
                    return None
                raw_name = f.read(fields["namesize"])
                if raw_name.rstrip(b"\x00") == CpioUtils.TRAILER_NAME.rstrip(b"\x00"):
                    return None
                name = raw_name.rstrip(b"\x00").decode("utf-8", errors="replace")
                data_start = f.tell()
                pad = (4 - (data_start % 4)) % 4
                data_start += pad
                if name == entry_name:
                    f.seek(data_start)
                    data = f.read(fields["filesize"])
                    _debug(f"read_file: found {entry_name} ({len(data)} bytes)")
                    return data
                f.seek(data_start + fields["filesize"])
                pad2 = (4 - (fields["filesize"] % 4)) % 4
                if pad2:
                    f.read(pad2)
        return None

    @staticmethod
    def has_file(archive_path, entry_name):
        _debug(f"has_file({os.path.basename(archive_path)}, {entry_name})")
        with open(archive_path, "rb") as f:
            while True:
                pos = f.tell()
                header = f.read(110)
                fields = CpioUtils._parse_header(header)
                if fields is None:
                    return False
                raw_name = f.read(fields["namesize"])
                if raw_name.rstrip(b"\x00") == CpioUtils.TRAILER_NAME.rstrip(b"\x00"):
                    return False
                name = raw_name.rstrip(b"\x00").decode("utf-8", errors="replace")
                if name == entry_name:
                    _debug(f"has_file: True")
                    return True
                data_start = f.tell()
                pad = (4 - (data_start % 4)) % 4
                data_start += pad
                f.seek(data_start + fields["filesize"])
                pad2 = (4 - (fields["filesize"] % 4)) % 4
                if pad2:
                    f.read(pad2)

    @staticmethod
    def _write_with_retry(write_fn):
        try:
            return write_fn()
        except PermissionError:
            pass
        if WSADetector.is_running():
            _log("Permission denied, stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        return write_fn()

    @staticmethod
    def replace_bytes(archive_path, old_bytes, new_bytes):
        _debug(f"replace_bytes({old_bytes[:30]} -> {new_bytes[:30]})")
        if len(old_bytes) != len(new_bytes):
            raise ValueError(f"replacement must be same byte count: {len(old_bytes)} != {len(new_bytes)}")
        with open(archive_path, "rb") as f:
            data = f.read()
        count = data.count(old_bytes)
        _debug(f"replace_bytes: found {count} occurrences")
        if count == 0:
            return 0
        new_data = data.replace(old_bytes, new_bytes, 1)
        def _do_write():
            with open(archive_path, "wb") as f:
                f.write(new_data)
        CpioUtils._write_with_retry(_do_write)
        return count

    @staticmethod
    def _find_trailer_offset(archive_path):
        with open(archive_path, "rb") as f:
            data = f.read()
        trailer_name = b"TRAILER!!!\x00"
        header_prefix = CpioUtils.MAGIC
        offset = 0
        while offset < len(data):
            if data[offset:offset + 6] == header_prefix:
                fields = CpioUtils._parse_header(data[offset:offset + 110])
                if fields is None:
                    break
                name_data = data[offset + 110:offset + 110 + fields["namesize"]]
                if name_data.rstrip(b"\x00") == trailer_name.rstrip(b"\x00"):
                    return offset
                pad1 = (4 - ((110 + fields["namesize"]) % 4)) % 4
                data_start = offset + 110 + fields["namesize"] + pad1
                pad2 = (4 - (fields["filesize"] % 4)) % 4
                offset = data_start + fields["filesize"] + pad2
            else:
                offset += 1
        return len(data)

    @staticmethod
    def add_file(archive_path, arcname, file_data, mode=0o100644):
        _debug(f"add_file({arcname}, {len(file_data)} bytes)")
        trailer_offset = CpioUtils._find_trailer_offset(archive_path)
        with open(archive_path, "rb") as f:
            before_trailer = f.read(trailer_offset)
        new_entry = CpioUtils._build_entry(arcname, file_data, mode=mode)
        trailer = CpioUtils._trailer_entry()
        def _do_write():
            with open(archive_path, "wb") as f:
                f.write(before_trailer)
                f.write(new_entry)
                f.write(trailer)
        CpioUtils._write_with_retry(_do_write)

    @staticmethod
    def add_symlink(archive_path, link_name, target):
        _debug(f"add_symlink({link_name} -> {target})")
        if isinstance(target, str):
            target = target.encode("utf-8")
        trailer_offset = CpioUtils._find_trailer_offset(archive_path)
        with open(archive_path, "rb") as f:
            before_trailer = f.read(trailer_offset)
        new_entry = CpioUtils._build_entry(link_name, target, mode=0o120777, nlink=1)
        trailer = CpioUtils._trailer_entry()
        def _do_write():
            with open(archive_path, "wb") as f:
                f.write(before_trailer)
                f.write(new_entry)
                f.write(trailer)
        CpioUtils._write_with_retry(_do_write)

    @staticmethod
    def add_files(archive_path, entries):
        _debug(f"add_files: {len(entries)} entries")
        for arcname, data, mode in entries:
            _debug(f"  {arcname} ({len(data)} bytes)")
        trailer_offset = CpioUtils._find_trailer_offset(archive_path)
        with open(archive_path, "rb") as f:
            before_trailer = f.read(trailer_offset)
        parts = [before_trailer]
        for arcname, file_data, mode in entries:
            parts.append(CpioUtils._build_entry(arcname, file_data, mode=mode))
        parts.append(CpioUtils._trailer_entry())
        def _do_write():
            with open(archive_path, "wb") as f:
                for part in parts:
                    f.write(part)
        CpioUtils._write_with_retry(_do_write)

    @staticmethod
    def delete_file(archive_path, entry_name):
        _debug(f"delete_file({entry_name})")
        entries = CpioUtils.scan_entries(archive_path)
        with open(archive_path, "rb") as f:
            data = f.read()
        parts = []
        for name, data_start, filesize, header_pos in entries:
            if name == entry_name:
                continue
            fields = CpioUtils._parse_header(data[header_pos:header_pos + 110])
            pad1 = (4 - ((110 + fields["namesize"]) % 4)) % 4
            entry_start = header_pos
            entry_end = data_start + filesize
            pad2 = (4 - (filesize % 4)) % 4
            entry_end += pad2
            parts.append(data[entry_start:entry_end])
        parts.append(CpioUtils._trailer_entry())
        def _do_write():
            with open(archive_path, "wb") as f:
                for part in parts:
                    f.write(part)
        CpioUtils._write_with_retry(_do_write)

    @staticmethod
    def read_all(archive_path):
        with open(archive_path, "rb") as f:
            raw = f.read()
        out = []
        for name, data_start, filesize, header_pos in CpioUtils.scan_entries(archive_path):
            fields = CpioUtils._parse_header(raw[header_pos:header_pos + 110])
            out.append((name, fields["mode"], raw[data_start:data_start + filesize]))
        return out

    @staticmethod
    def parent_dirs(arcname):
        parts = arcname.strip("/").split("/")
        return ["/".join(parts[:i]) for i in range(1, len(parts))]

    @staticmethod
    def ensure_dir_entries(archive_path, dirs, dir_mode=0o040750):
        """Guarantee each dir exists as a cpio dir entry placed before all of
        its descendants. Rewrites the archive only when that is not already
        true; untouched entries keep their bytes (mode, uid, gid, mtime)."""
        dirs = [d.strip("/") for d in dirs if d.strip("/")]
        if not dirs:
            return False
        with open(archive_path, "rb") as f:
            raw = f.read()
        chunks = []
        for name, data_start, filesize, header_pos in CpioUtils.scan_entries(archive_path):
            pad2 = (4 - (filesize % 4)) % 4
            chunks.append((name, raw[header_pos:data_start + filesize + pad2]))
        wanted = set(dirs)
        names = [n for n, _ in chunks]
        for d in dirs:
            if d not in names:
                break
            di = names.index(d)
            if any(n.startswith(d + "/") and i < di for i, n in enumerate(names)):
                break
        else:
            _debug(f"ensure_dir_entries: {dirs} already ordered")
            return False
        _debug(f"ensure_dir_entries: rebuilding for {dirs}")
        result = [(n, c) for n, c in chunks if n not in wanted]
        for d in sorted(dirs, key=lambda p: p.count("/")):
            idx = len(result)
            for i, (n, _c) in enumerate(result):
                if n.startswith(d + "/"):
                    idx = i
                    break
            orig = next((c for n, c in chunks if n == d), None)
            chunk = orig if orig is not None else CpioUtils._build_entry(d, b"", mode=dir_mode)
            result.insert(idx, (d, chunk))
        def _do_write():
            with open(archive_path, "wb") as f:
                for _n, c in result:
                    f.write(c)
                f.write(CpioUtils._trailer_entry())
        CpioUtils._write_with_retry(_do_write)
        return True

    @staticmethod
    def list_entries(archive_path):
        """[(name, mode, filesize)] for every entry.

        scan_entries() does not decode the mode, so the GUI cannot tell a
        file from a folder or a symlink without this.
        """
        _debug(f"list_entries({os.path.basename(archive_path)})")
        entries = []
        with open(archive_path, "rb") as f:
            while True:
                header = f.read(110)
                fields = CpioUtils._parse_header(header)
                if fields is None:
                    break
                raw_name = f.read(fields["namesize"])
                if raw_name.rstrip(b"\x00") == CpioUtils.TRAILER_NAME.rstrip(b"\x00"):
                    break
                name = raw_name.rstrip(b"\x00").decode("utf-8", errors="replace")
                data_start = f.tell()
                pad = (4 - (data_start % 4)) % 4
                data_start += pad
                entries.append((name, fields["mode"], fields["filesize"]))
                f.seek(data_start + fields["filesize"])
                pad2 = (4 - (fields["filesize"] % 4)) % 4
                if pad2:
                    f.read(pad2)
        _debug(f"list_entries: found {len(entries)} entries")
        return entries

    @staticmethod
    def overwrite_file(archive_path, arcname, file_data, mode=None):
        """Replace an existing entry's payload.

        add_file() alone would just append a second entry with the same name,
        so the old one is dropped first.
        """
        _debug(f"overwrite_file({arcname}, {len(file_data)} bytes)")
        if CpioUtils.has_file(archive_path, arcname):
            CpioUtils.delete_file(archive_path, arcname)
        if mode is None:
            mode = guess_mode(arcname, file_data)
        CpioUtils.add_file(archive_path, arcname, file_data, mode=mode)

    @staticmethod
    def delete_tree(archive_path, arcname):
        """Drop one entry and every descendant under arcname/."""
        arcname = arcname.strip("/")
        prefix = arcname + "/"
        _debug(f"delete_tree({arcname})")
        entries = CpioUtils.scan_entries(archive_path)
        victims = {name for name, *_ in entries if name == arcname or name.startswith(prefix)}
        if not victims:
            _debug(f"delete_tree({arcname}): nothing to remove")
            return 0
        with open(archive_path, "rb") as f:
            data = f.read()
        parts = []
        for name, data_start, filesize, header_pos in entries:
            if name in victims:
                continue
            fields = CpioUtils._parse_header(data[header_pos:header_pos + 110])
            entry_end = data_start + filesize
            pad2 = (4 - (filesize % 4)) % 4
            entry_end += pad2
            parts.append(data[header_pos:entry_end])
        parts.append(CpioUtils._trailer_entry())
        def _do_write():
            with open(archive_path, "wb") as f:
                for part in parts:
                    f.write(part)
        CpioUtils._write_with_retry(_do_write)
        _debug(f"delete_tree({arcname}): removed {len(victims)} entries")
        return len(victims)

    @staticmethod
    def rename_entry(archive_path, old, new):
        """Move an entry, carrying its whole subtree when it is a folder.

        cpio has no rename op, so this is read -> delete -> re-add under the
        new name. Raises ValueError when the destination is already taken.
        """
        old = old.strip("/")
        new = new.strip("/")
        _debug(f"rename_entry({old} -> {new})")
        if not old or not new or old == new:
            return False
        modes = {name: mode for name, mode, _size in CpioUtils.list_entries(archive_path)}
        if old not in modes:
            raise ValueError(f"not found in image: {old}")
        if any(name == new or name.startswith(new + "/") for name in modes):
            raise ValueError(f"already exists: {new}")
        is_dir = any(name.startswith(old + "/") for name in modes)
        prefix = old + "/"
        moved = []
        for name, mode, _size in CpioUtils.list_entries(archive_path):
            if name == old:
                dest = new
            elif is_dir and name.startswith(prefix):
                dest = new + "/" + name[len(prefix):]
            else:
                continue
            payload = CpioUtils.read_file(archive_path, name)
            moved.append((dest, payload if payload is not None else b"", mode))
        if not moved:
            raise ValueError(f"not found in image: {old}")
        CpioUtils.delete_tree(archive_path, old)
        CpioUtils.add_files(archive_path, moved)
        dirs = CpioUtils.parent_dirs(new)
        if is_dir:
            dirs.append(new)
        CpioUtils.ensure_dir_entries(archive_path, sorted(set(dirs)), 0o040755)
        _debug(f"rename_entry: moved {len(moved)} entries")
        return True

    @staticmethod
    def extract_to(archive_path, dest_dir, names=None):
        """Write entries out to dest_dir; names=None extracts everything.

        Files keep their permission bits, symlinks are recreated as symlinks,
        and descendants of a selected folder come along automatically.
        """
        wanted = None if names is None else {n.strip("/") for n in names}
        _debug(f"extract_to({dest_dir}, names={wanted})")
        os.makedirs(dest_dir, exist_ok=True)
        count = 0
        for name, mode, data in CpioUtils.read_all(archive_path):
            bare = name.strip("/")
            if not bare or bare in (".", "..") or bare == "TRAILER!!!":
                continue
            if wanted is not None and not any(
                    bare == w or bare.startswith(w + "/") for w in wanted):
                continue
            target = os.path.join(dest_dir, *bare.split("/"))
            parent = os.path.dirname(target) or dest_dir
            kind = mode & 0o170000
            if kind == 0o040000:
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(parent, exist_ok=True)
            if kind == 0o120000:
                if os.path.lexists(target):
                    os.remove(target)
                try:
                    os.symlink(data.decode("utf-8", errors="replace"), target)
                except OSError:
                    with open(target, "wb") as f:
                        f.write(data)
            else:
                with open(target, "wb") as f:
                    f.write(data)
                try:
                    os.chmod(target, mode & 0o7777)
                except OSError:
                    pass
            count += 1
        _debug(f"extract_to: wrote {count} entries")
        return count


class ApkAnalyzer:

    @staticmethod
    def _run_aaptpp(args_list):
        if not os.path.exists(AAPT_PP):
            return ""
        try:
            cmd = [AAPT_PP] + args_list
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=10, creationflags=CREATE_NO_WINDOW)
            lines = r.stdout.strip().split("\n")
            out = []
            skip_header = True
            for line in lines:
                if skip_header:
                    if line.startswith("===") or not line.strip():
                        continue
                    skip_header = False
                out.append(line)
            return "\n".join(out).strip()
        except Exception as e:
            _debug(f"_run_aaptpp error: {e}")
            return ""

    @staticmethod
    def get_package_name(apk_path):
        _debug(f"ApkAnalyzer.get_package_name({os.path.basename(apk_path)})")
        raw = ApkAnalyzer._run_aaptpp(["package", apk_path])
        pkg = raw.strip().split("\n")[-1].strip() if raw else ""
        if pkg and "." in pkg:
            _debug(f"  -> {pkg}")
            return pkg
        fallback = Path(apk_path).stem
        _debug(f"  -> fallback: {fallback}")
        return fallback

    @staticmethod
    def get_app_label(apk_path):
        _debug(f"ApkAnalyzer.get_app_label({os.path.basename(apk_path)})")
        raw = ApkAnalyzer._run_aaptpp(["app-name", apk_path])
        label = raw.strip().split("\n")[-1].strip() if raw else ""
        if label:
            _debug(f"  -> {label}")
            return label
        return Path(apk_path).stem
    @staticmethod
    def get_all_info(apk_path):
        _debug(f"ApkAnalyzer.get_all_info({os.path.basename(apk_path)})")
        pkg = ApkAnalyzer.get_package_name(apk_path)
        label = ApkAnalyzer.get_app_label(apk_path)
        return {"package": pkg, "label": label, "apk_path": apk_path}


class InitrdManager:

    def __init__(self, initrd_path):
        self.path = initrd_path
        _debug(f"InitrdManager({os.path.basename(initrd_path)})")

    def has_info_json(self):
        result = CpioUtils.has_file(self.path, "info.json")
        _debug(f"has_info_json() -> {result}")
        return result

    def read_info(self):
        _debug("read_info()")
        data = CpioUtils.read_file(self.path, "info.json")
        if not data:
            return None
        try:
            info = json.loads(data.decode("utf-8"))
            _debug(f"read_info: {info}")
            return info
        except Exception:
            _debug(f"read_info: parse error")
            return None

    def get_recovery_flag(self):
        info = self.read_info()
        if info is None:
            _debug("get_recovery_flag() -> False (no info)")
            return False
        raw = info.get("recovery_flag", "false")
        if isinstance(raw, str):
            flag = raw.strip().lower() == "true"
        else:
            flag = bool(raw)
        _debug(f"get_recovery_flag() -> {flag}")
        return flag

    def set_recovery_flag(self, value=True):
        _debug(f"set_recovery_flag({value})")
        if value:
            for old in CpioUtils.FLAG_FALSE:
                for new in CpioUtils.FLAG_TRUE:
                    result = CpioUtils.replace_bytes(self.path, old, new)
                    if result:
                        _debug(f"set_recovery_flag: {result} replacements ({old!r} -> {new!r})")
                        return result
        else:
            for old in CpioUtils.FLAG_TRUE:
                for new in CpioUtils.FLAG_FALSE:
                    result = CpioUtils.replace_bytes(self.path, old, new)
                    if result:
                        _debug(f"set_recovery_flag: {result} replacements ({old!r} -> {new!r})")
                        return result
        _debug("set_recovery_flag: no pattern matched")
        # The byte pairs only cover the shipped spacing ("true" with a
        # trailing space); fall back to a targeted rewrite for every other
        # layout so Enable/Disable keeps working after info.json is re-saved.
        data = CpioUtils.read_file(self.path, "info.json")
        if not data:
            _debug("set_recovery_flag fallback: no info.json")
            return 0
        wanted = b'"true"' if value else b'"false"'
        new_data, count = RECOVERY_FLAG_RE.subn(
            lambda m: m.group(1) + wanted, data, count=1)
        if not count or new_data == data:
            _debug("set_recovery_flag fallback: nothing to change")
            return 0
        mode = None
        for name, entry_mode, _size in CpioUtils.list_entries(self.path):
            if name == "info.json":
                mode = entry_mode
                break
        CpioUtils.overwrite_file(self.path, "info.json", new_data, mode=mode)
        _debug("set_recovery_flag fallback: info.json rewritten")
        return 1

    def get_twrp_support(self):
        info = self.read_info()
        if info is None:
            _debug("get_twrp_support() -> False (no info)")
            return False
        raw = info.get("twrp_support", "false")
        if isinstance(raw, str):
            flag = raw.strip().lower() == "true"
        else:
            flag = bool(raw)
        _debug(f"get_twrp_support() -> {flag}")
        return flag

    def set_twrp_support(self, value=True):
        """Rewrite the twrp_support key inside info.json.

        A targeted regex on the raw payload keeps every other byte of the
        entry (notably the recovery_flag pattern set_recovery_flag() hunts
        for) exactly as it was; only the matched value is swapped."""
        _debug(f"set_twrp_support({value})")
        data = CpioUtils.read_file(self.path, "info.json")
        if not data:
            _debug("set_twrp_support: no info.json")
            return 0
        wanted = b'"true"' if value else b'"false"'
        new_data, count = TWRP_FLAG_RE.subn(
            lambda m: m.group(1) + wanted, data, count=1)
        if not count:
            _debug("set_twrp_support: twrp_support key not found")
            return 0
        if new_data == data:
            _debug("set_twrp_support: already in that state")
            return 0
        mode = None
        for name, entry_mode, _size in CpioUtils.list_entries(self.path):
            if name == "info.json":
                mode = entry_mode
                break
        CpioUtils.overwrite_file(self.path, "info.json", new_data, mode=mode)
        _debug("set_twrp_support: info.json rewritten")
        return 1

    def is_stock(self):
        result = not self.has_info_json()
        _debug(f"is_stock() -> {result}")
        return result

    def twrp_missing(self):
        """Required TWRP paths absent from the image (empty list = complete)."""
        entries = {name for name, *_ in CpioUtils.scan_entries(self.path)}
        missing = []
        for path in TWRP_REQUIRED_FILES:
            if path.strip("/") not in entries:
                missing.append(path)
        for path in TWRP_REQUIRED_DIRS:
            key = path.strip("/") + "/"
            if not any(name.startswith(key) for name in entries):
                missing.append(key)
        _debug(f"twrp_missing() -> {missing}")
        return missing

    def is_twrp_supported(self):
        info = self.read_info()
        if info is None:
            result = False
        else:
            raw = info.get("twrp_support", "false")
            if isinstance(raw, str):
                flag = raw.strip().lower() == "true"
            else:
                flag = bool(raw)
            result = flag and not self.twrp_missing()
        _debug(f"is_twrp_supported() -> {result}")
        return result

    def inject_from_7z(self, seven_zip_path):
        _debug(f"inject_from_7z({seven_zip_path})")
        tmpdir = INJECT_TEMP
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
        os.makedirs(tmpdir, exist_ok=True)
        try:
            subprocess.run(
                [SEVEN_ZIP, "x", seven_zip_path, f"-o{tmpdir}", "-y"],
                capture_output=True, timeout=30,
                creationflags=CREATE_NO_WINDOW)
            entries_to_add = []
            for root, _dirs, files in os.walk(tmpdir):
                for fname in files:
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, tmpdir).replace("\\", "/")
                    with open(full, "rb") as f:
                        data = f.read()
                    entries_to_add.append((arcname, data, guess_mode(arcname, data)))
            if not entries_to_add:
                raise RuntimeError("TWRP archive is empty")
            existing = {}
            for name, _ds, _sz, _hp in CpioUtils.scan_entries(self.path):
                existing[name] = True
            new_entries = []
            for arcname, data, mode in entries_to_add:
                if arcname in existing:
                    _debug(f"  Replacing existing: {arcname}")
                    CpioUtils.delete_file(self.path, arcname)
                new_entries.append((arcname, data, mode))
            if new_entries:
                CpioUtils.add_files(self.path, new_entries)
            dirs = sorted({d for arcname, _d, _m in entries_to_add
                           for d in CpioUtils.parent_dirs(arcname)})
            CpioUtils.ensure_dir_entries(self.path, dirs, 0o040755)
            _log(f"Injected {len(entries_to_add)} files from 7z")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _dest_join(self, dest, name):
        dest = dest.strip("/")
        if dest:
            return f"{dest}/{name}"
        return name

    def inject_file(self, src_path, dest="/"):
        _debug(f"inject_file({src_path}, dest={dest})")
        arcname = self._dest_join(dest, os.path.basename(src_path))
        _debug(f"  arcname: {arcname}")
        with open(src_path, "rb") as f:
            data = f.read()
        existing = {name for name, *_ in CpioUtils.scan_entries(self.path)}
        if arcname in existing:
            _debug(f"  Replacing existing: {arcname}")
            CpioUtils.delete_file(self.path, arcname)
        mode = guess_mode(arcname, data)
        CpioUtils.add_file(self.path, arcname, data, mode=mode)
        CpioUtils.ensure_dir_entries(self.path, CpioUtils.parent_dirs(arcname), 0o040755)
        _log(f"Injected {arcname} ({len(data):,} bytes, {mode & 0o7777:o})")

    def inject_folder(self, src_folder, dest="/"):
        _debug(f"inject_folder({src_folder}, dest={dest})")
        entries_to_add = []
        src_folder = os.path.normpath(src_folder)
        for root, _dirs, files in os.walk(src_folder):
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, src_folder).replace("\\", "/")
                arcname = self._dest_join(dest, rel)
                with open(full, "rb") as f:
                    data = f.read()
                entries_to_add.append((arcname, data, guess_mode(arcname, data)))
        existing = {name for name, *_ in CpioUtils.scan_entries(self.path)}
        new_entries = []
        for arcname, data, mode in entries_to_add:
            if arcname in existing:
                _debug(f"  Replacing existing: {arcname}")
                CpioUtils.delete_file(self.path, arcname)
            new_entries.append((arcname, data, mode))
        if new_entries:
            CpioUtils.add_files(self.path, new_entries)
        dirs = sorted({d for arcname, _d, _m in entries_to_add
                       for d in CpioUtils.parent_dirs(arcname)})
        CpioUtils.ensure_dir_entries(self.path, dirs, 0o040755)
        _log(f"Injected {len(entries_to_add)} files from folder")

    def inject_7z_with_patch(self, seven_zip_path, dest="/"):
        _debug(f"inject_7z_with_patch({seven_zip_path}, dest={dest})")
        tmpdir = INJECT_TEMP
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
        os.makedirs(tmpdir, exist_ok=True)
        try:
            _debug(f"Extracting: {seven_zip_path} -> {tmpdir}")
            result = subprocess.run(
                [SEVEN_ZIP, "x", seven_zip_path, f"-o{tmpdir}", "-y"],
                capture_output=True, text=True, timeout=30,
                creationflags=CREATE_NO_WINDOW)
            if result.returncode != 0:
                _debug(f"7z extract FAILED: {result.stderr}")
            else:
                _debug(f"7z extract OK")

            _debug("Temp folder contents:")
            for root, dirs, files in os.walk(tmpdir):
                for fname in files:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, tmpdir)
                    fsize = os.path.getsize(full)
                    _debug(f"  {rel} ({fsize:,} bytes)")

            patch_path = os.path.join(tmpdir, "patch.json")
            if os.path.exists(patch_path):
                _log(f"Reading patch.json")
                _debug(f"Path: {patch_path}")
                with open(patch_path, "r") as f:
                    patch = json.load(f)

                existing = {name for name, *_ in CpioUtils.scan_entries(self.path)}

                pick_items = [item for item in patch if "pick" in item]
                _log(f"Injecting {len(pick_items)} entries")

                entries_to_add = []
                for item in pick_items:
                    pick = item["pick"].strip("/")
                    drop = item["drop"].strip("/")
                    pick_full = os.path.join(tmpdir, pick.replace("/", os.sep))
                    _debug(f"  Processing: pick={pick}, drop={drop}")
                    _debug(f"    Source: {pick_full}")
                    if os.path.isdir(pick_full):
                        _debug(f"    Type: DIRECTORY")
                        for root, _dirs, files in os.walk(pick_full):
                            for fname in files:
                                full = os.path.join(root, fname)
                                rel = os.path.relpath(full, pick_full).replace("\\", "/")
                                arcname = f"{drop}/{pick}/{rel}".strip("/")
                                with open(full, "rb") as f:
                                    data = f.read()
                                entries_to_add.append((arcname, data, guess_mode(arcname, data)))
                                _debug(f"      -> {arcname} ({len(data):,} bytes)")
                    elif os.path.isfile(pick_full):
                        arcname = f"{drop}/{os.path.basename(pick)}".strip("/")
                        with open(pick_full, "rb") as f:
                            data = f.read()
                        entries_to_add.append((arcname, data, guess_mode(arcname, data)))
                        _debug(f"    Type: FILE -> {arcname} ({len(data):,} bytes)")
                    else:
                        _debug(f"    WARNING: source not found!")

                _debug(f"Total entries to inject: {len(entries_to_add)}")
                new_entries = []
                for arcname, data, mode in entries_to_add:
                    if arcname in existing:
                        _debug(f"  Replacing existing: {arcname}")
                        CpioUtils.delete_file(self.path, arcname)
                    new_entries.append((arcname, data, mode))
                if new_entries:
                    CpioUtils.add_files(self.path, new_entries)
                dirs = sorted({d for arcname, _d, _m in entries_to_add
                               for d in CpioUtils.parent_dirs(arcname)})
                CpioUtils.ensure_dir_entries(self.path, dirs, 0o040755)
                _log(f"Injection complete")
            else:
                raise RuntimeError("TWRP archive has no patch.json — rejected")
        finally:
            _debug(f"Cleaning temp: {tmpdir}")
            shutil.rmtree(tmpdir, ignore_errors=True)

    def add_hook_infrastructure(self):
        _debug("add_hook_infrastructure()")
        if not os.path.exists(ASSET_FIX_7Z):
            _debug(f"fix.7z not found: {ASSET_FIX_7Z}")
            return False
        existing_entries = {name for name, *_ in CpioUtils.scan_entries(self.path)}
        if POSTFSDATA_ARCNAME in existing_entries:
            _log("Magisk already installed, skipping hook infrastructure")
            return True
        if os.path.exists(FIX_TEMP):
            shutil.rmtree(FIX_TEMP, ignore_errors=True)
        os.makedirs(FIX_TEMP, exist_ok=True)
        try:
            subprocess.run(
                [SEVEN_ZIP, "x", ASSET_FIX_7Z, f"-o{FIX_TEMP}", "-y"],
                capture_output=True, timeout=30,
                creationflags=CREATE_NO_WINDOW)

            _log("Adding Magisk hook infrastructure")

            CpioUtils.delete_file(self.path, "init")
            _log("  Deleted /init")

            CpioUtils.ensure_dir_entries(self.path, HOOK_DIRS, HOOK_DIR_MODE)
            _log("  " + " ".join(f"{d}/" for d in HOOK_DIRS) + " (dir entries)")

            existing = {name for name, *_ in CpioUtils.scan_entries(self.path)}
            count = 0
            for root, _dirs, files in os.walk(FIX_TEMP):
                for fname in files:
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, FIX_TEMP).replace("\\", "/")
                    if arcname == "init":
                        _debug(f"  Skipping {arcname} from fix.7z (will create symlink)")
                        continue
                    if arcname in existing:
                        CpioUtils.delete_file(self.path, arcname)
                    with open(full, "rb") as f:
                        data = f.read()
                    if arcname == POSTFSDATA_ARCNAME:
                        data = patch_postfsdata(data)
                    mode = guess_mode(arcname, data)
                    CpioUtils.add_file(self.path, arcname, data, mode=mode)
                    _log(f"  {arcname} ({len(data):,} bytes, {mode & 0o7777:o})")
                    count += 1

            CpioUtils.ensure_dir_entries(self.path, HOOK_DIRS, HOOK_DIR_MODE)

            CpioUtils.add_symlink(self.path, "init", "lspinit")
            _log("  init -> lspinit (symlink)")
            count += 1

            if ".backup" not in existing:
                CpioUtils.add_file(self.path, ".backup", b"", mode=0o040755)
                _log("  .backup/ (empty dir)")
                count += 1

            _log(f"Injected {count} files from fix.7z")
            return True
        finally:
            shutil.rmtree(FIX_TEMP, ignore_errors=True)

    def hook_issues(self):
        """Read-only audit of the installed hook. Returns a list of human
        readable problems (empty when everything is correct)."""
        issues = []
        entries = CpioUtils.read_all(self.path)
        modes = {n: m for n, m, _d in entries}
        names = [n for n, _m, _d in entries]

        for d in HOOK_DIRS:
            if d not in names:
                issues.append(f"missing directory entry: {d}/")
                continue
            di = names.index(d)
            if any(n.startswith(d + "/") and i < di for i, n in enumerate(names)):
                issues.append(f"directory entry out of order: {d}/")

        for arcname, want in HOOK_MODES.items():
            if arcname not in modes:
                issues.append(f"missing entry: {arcname}")
                continue
            if modes[arcname] != want:
                issues.append(
                    f"wrong mode on {arcname}: "
                    f"{modes[arcname] & 0o7777:o} (expected {want & 0o7777:o})")

        data = {n: d for n, _m, d in entries}
        if POSTFSDATA_ARCNAME in data:
            if data[POSTFSDATA_ARCNAME] != patch_postfsdata(data[POSTFSDATA_ARCNAME]):
                size = len(data[POSTFSDATA_ARCNAME])
                issues.append(
                    f"{POSTFSDATA_ARCNAME} missing uninstall handler "
                    f"({size:,} bytes)")
        return issues

    def repair_hook_infrastructure(self):
        """Fix whatever hook_issues() reported. Safe to call repeatedly."""
        issues = self.hook_issues()
        if not issues:
            _debug("repair_hook_infrastructure: nothing to fix")
            return []
        _log("Repairing Magisk hook infrastructure")

        for name, mode, data in CpioUtils.read_all(self.path):
            want = HOOK_MODES.get(name, mode)
            fixed = patch_postfsdata(data) if name == POSTFSDATA_ARCNAME else data
            if mode == want and fixed == data:
                continue
            CpioUtils.delete_file(self.path, name)
            CpioUtils.add_file(self.path, name, fixed, mode=want)
            if mode != want:
                _log(f"  {name}: mode {mode & 0o7777:o} -> {want & 0o7777:o}")
            if fixed != data:
                _log(f"  {name}: {len(data):,} -> {len(fixed):,} bytes "
                     f"(uninstall handler added)")

        if CpioUtils.ensure_dir_entries(self.path, HOOK_DIRS, HOOK_DIR_MODE):
            _log("  " + " ".join(f"{d}/" for d in HOOK_DIRS) + ": directory entries inserted")

        remaining = self.hook_issues()
        if remaining:
            _log("  WARNING: still incorrect after repair:")
            for issue in remaining:
                _log(f"    {issue}")
        return issues

    def override_hook_infrastructure(self):
        """Force a full rebuild of the hook from fix.7z, discarding whatever
        is already installed. Returns True only if the result passes hook_issues()."""
        _debug("override_hook_infrastructure()")
        names = [n for n, *_ in CpioUtils.scan_entries(self.path)]
        for target in (POSTFSDATA_ARCNAME, ".backup"):
            if target not in names:
                continue
            if any(n.startswith(target + "/") for n in names):
                _debug(f"  keeping {target} (has children)")
                continue
            CpioUtils.delete_file(self.path, target)
            _log(f"  Removed existing {target} (forcing rebuild)")
            names.remove(target)
        if not self.add_hook_infrastructure():
            _log("Failed to rebuild Magisk hook!")
            return False
        remaining = self.hook_issues()
        if remaining:
            _log("  WARNING: rebuild left problems:")
            for issue in remaining:
                _log(f"    {issue}")
            return False
        return True

    @staticmethod
    def get_package_name(apk_path):
        _debug(f"get_package_name({apk_path})")
        aapt = resource_path(os.path.join("assets", "aaptpp.exe"))
        if os.path.exists(aapt):
            try:
                r = subprocess.run(
                    [aapt, "package", apk_path],
                    capture_output=True, text=True, timeout=10,
                    creationflags=CREATE_NO_WINDOW)
                pkg = r.stdout.strip()
                if pkg and "." in pkg:
                    _debug(f"get_package_name: {pkg}")
                    return pkg
            except Exception as e:
                _debug(f"get_package_name aaptpp error: {e}")
        fallback = Path(apk_path).stem
        _debug(f"get_package_name fallback: {fallback}")
        return fallback

    def has_lsp_image(self):
        result = CpioUtils.has_file(self.path, f"overlay.d/sbin/{LSP_IMAGE_NAME}")
        _debug(f"has_lsp_image() -> {result}")
        return result

    @staticmethod
    def generate_privapp_xml_multi(pkg_perms):
        """One <permissions> file with a <privapp-permissions> block per package.

        pkg_perms: {package_name: [perm, ...]}. Packages are sorted so the
        output is stable; installing another app merges, never replaces."""
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            "<permissions>",
        ]
        for pkg in sorted(pkg_perms):
            lines.append(f'    <privapp-permissions package="{pkg}">')
            for perm in pkg_perms[pkg]:
                lines.append(f'        <permission name="{perm}"/>')
            lines.append("    </privapp-permissions>")
        lines.append("</permissions>")
        return "\n".join(lines)

    @staticmethod
    def generate_default_xml_multi(pkg_data):
        """One <exceptions> file with an <exception> block per package.

        pkg_data: {package_name: (runtime_perms, fixed_perms)} - fixed is
        tracked per package, not shared across packages."""
        lines = [
            "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>",
            "<exceptions>",
        ]
        for pkg in sorted(pkg_data):
            runtime_perms, fixed_perms = pkg_data[pkg]
            lines.append(f'    <exception package="{pkg}">')
            for perm in runtime_perms:
                fixed = "true" if perm in fixed_perms else "false"
                lines.append(f'        <permission name="{perm}" fixed="{fixed}"/>')
            lines.append("    </exception>")
        lines.append("</exceptions>")
        return "\n".join(lines)

    @staticmethod
    def generate_privapp_xml(package_name, privapp_perms):
        return InitrdManager.generate_privapp_xml_multi(
            {package_name: list(privapp_perms)})

    @staticmethod
    def generate_default_xml(package_name, runtime_perms, fixed_perms=None):
        return InitrdManager.generate_default_xml_multi(
            {package_name: (list(runtime_perms),
                            set() if fixed_perms is None else set(fixed_perms))})

    @staticmethod
    def _load_permission_profiles(extract_dir):
        """{package: profile} from an extracted image's permissions/*.json."""
        profiles = {}
        perm_dir = os.path.join(extract_dir, "permissions")
        if not os.path.isdir(perm_dir):
            return profiles
        for name in sorted(os.listdir(perm_dir)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(perm_dir, name), encoding="utf-8") as f:
                    profiles[name[:-5]] = json.load(f)
            except (OSError, ValueError) as exc:
                _debug(f"  profile permissions/{name} unreadable: {exc}")
        return profiles

    @staticmethod
    def _foreign_blocks(xml_path, decided_pkgs, tag):
        """Top-level <tag package=...> elements we cannot derive ourselves.

        A block whose package has no permissions/*.json AND was not explicitly
        removed comes from a legacy image - it is preserved verbatim when the
        file is rebuilt."""
        kept = []
        if not os.path.isfile(xml_path):
            return kept
        try:
            root = ET.parse(xml_path).getroot()
        except (ET.ParseError, OSError) as exc:
            _debug(f"  {os.path.basename(xml_path)} unreadable ({exc}), "
                   "rebuilding from profiles")
            return kept
        for el in root:
            pkg = el.get("package")
            if el.tag == tag and pkg and pkg not in decided_pkgs:
                kept.append(el)
        return kept

    @staticmethod
    def regenerate_permission_xmls(extract_dir, removed_pkgs=()):
        """Rebuild BOTH merged permission XMLs of one extracted module image.

        Every package with permissions/*.json gets its own block inside the
        single fixed-filename file (installing app B keeps app A's block).
        removed_pkgs: packages being uninstalled - their JSON is already gone,
        so their blocks must be dropped instead of treated as legacy. Blocks of
        unknown packages are preserved. Returns ({privapp packages},
        {exception packages}) now represented in the files; a file whose blocks
        all disappeared is deleted."""
        profiles = InitrdManager._load_permission_profiles(extract_dir)
        for gone in removed_pkgs:
            profiles.pop(gone, None)
        decided = set(profiles) | set(removed_pkgs)
        priv_map = {}
        def_map = {}
        for pkg, profile in profiles.items():
            priv = profile.get("privapp_perms") or []
            runtime = profile.get("runtime_perms") or []
            fixed = set(profile.get("fixed_runtime_perms") or [])
            if priv:
                priv_map[pkg] = list(priv)
            if runtime:
                def_map[pkg] = (list(runtime), fixed)

        # --- privapp XML ---
        priv_path = os.path.join(extract_dir, "system", "etc", "permissions",
                                 LSP_PRIV_XML)
        priv_kept = InitrdManager._foreign_blocks(
            priv_path, decided, "privapp-permissions")
        if priv_map or priv_kept:
            os.makedirs(os.path.dirname(priv_path), exist_ok=True)
            lines = ['<?xml version="1.0" encoding="utf-8"?>', "<permissions>"]
            for el in priv_kept:
                lines.append("    " + ET.tostring(el, encoding="unicode").rstrip())
            lines.extend(InitrdManager.generate_privapp_xml_multi(priv_map)
                         .splitlines()[2:-1])
            lines.append("</permissions>")
            with open(priv_path, "w", newline="") as f:
                f.write("\n".join(lines))
            n_priv = sum(len(v) for v in priv_map.values())
            _debug(f"  Generated {LSP_PRIV_XML} "
                   f"({len(priv_map)} packages, {n_priv} perms)")
        elif os.path.isfile(priv_path):
            os.remove(priv_path)
            _debug(f"  Removed {LSP_PRIV_XML} (no packages left)")

        # --- default-permissions XML ---
        def_path = os.path.join(extract_dir, "system", "etc",
                                "default-permissions", LSP_DEF_XML)
        def_kept = InitrdManager._foreign_blocks(
            def_path, decided, "exception")
        if def_map or def_kept:
            os.makedirs(os.path.dirname(def_path), exist_ok=True)
            lines = ["<?xml version='1.0' encoding='utf-8' standalone='yes' ?>",
                     "<exceptions>"]
            for el in def_kept:
                lines.append("    " + ET.tostring(el, encoding="unicode").rstrip())
            lines.extend(InitrdManager.generate_default_xml_multi(def_map)
                         .splitlines()[2:-1])
            lines.append("</exceptions>")
            with open(def_path, "w", newline="") as f:
                f.write("\n".join(lines))
            n_def = sum(len(v[0]) for v in def_map.values())
            _debug(f"  Generated {LSP_DEF_XML} "
                   f"({len(def_map)} packages, {n_def} perms)")
        elif os.path.isfile(def_path):
            os.remove(def_path)
            _debug(f"  Removed {LSP_DEF_XML} (no packages left)")

        return set(priv_map), set(def_map)

    def create_lsp_image(self, apk_paths, permission_profiles=None):
        _debug(f"create_lsp_image({len(apk_paths)} APKs)")
        if permission_profiles is None:
            permission_profiles = {}
        if os.path.exists(LSP_TEMP):
            shutil.rmtree(LSP_TEMP, ignore_errors=True)
        os.makedirs(LSP_TEMP, exist_ok=True)
        try:
            module_prop = (
                f"id={LSP_MOD_ID}\n"
                f"name={LSP_MOD_NAME}\n"
                "version=v1.0\n"
                "versionCode=1\n"
                "author=MR CYBER\n"
                f"description={LSP_MOD_DESC}\n"
            )
            with open(os.path.join(LSP_TEMP, "module.prop"), "w", newline="") as f:
                f.write(module_prop)
            post_fs_data = (
                "#!/bin/sh\n"
                "LOGFILE=\"$(dirname \"$0\")/post-fs-data.log\"\n"
                "log() { echo \"[$(date '+%Y-%m-%d %H:%M:%S')] $1\" | tee -a \"$LOGFILE\"; }\n"
                "log \"=== post-fs-data.sh start ===\"\n"
                'BASE="$(dirname "$0")"\n'
                "NVBASE=/data/adb\n"
                'MOD_UPDATE_DIRNAME=modules_update\n'
                'MODULE_UPDATE_ROOT=$NVBASE/$MOD_UPDATE_DIRNAME\n'
                "grep_prop() {\n"
                '    dos2unix <"$2" | sed -n "s/^$1=//p" | head -n 1\n'
                "}\n"
                'MODID=$(grep_prop id "$BASE"/module.prop)\n'
                'MOD_UPDATE_PATH=$MODULE_UPDATE_ROOT/$MODID\n'
                'MOD_PATH=$NVBASE/modules/$MODID\n'
                "log \"MODID=$MODID\"\n"
                "log \"BASE=$BASE\"\n"
                "log \"MOD_PATH=$MOD_PATH\"\n"
                "log \"MOD_UPDATE_PATH=$MOD_UPDATE_PATH\"\n"
                'mkdir -p -m 0755 "$MOD_PATH"\n'
                'chcon u:object_r:system_file:s0 "$MOD_PATH"\n'
                "log \"Created MOD_PATH\"\n"
                'cp -dr --preserve=all "$BASE/module.prop" "$MOD_PATH"\n'
                'chown root:root "$MOD_PATH/module.prop"\n'
                'chmod 644 "$MOD_PATH/module.prop"\n'
                'touch "$MOD_PATH/update"\n'
                "log \"Copied module.prop to MOD_PATH\"\n"
                'mkdir -p -m 0755 "$MOD_UPDATE_PATH"\n'
                'chcon u:object_r:system_file:s0 "$MOD_UPDATE_PATH"\n'
                'cp -dr --preserve=all "$BASE/module.prop" "$MOD_UPDATE_PATH"\n'
                'chown root:root "$MOD_UPDATE_PATH/module.prop"\n'
                'chmod 644 "$MOD_UPDATE_PATH/module.prop"\n'
                "log \"Copied module.prop to MOD_UPDATE_PATH\"\n"
                'cp -dr --preserve=all "$BASE/system" "$MOD_UPDATE_PATH"\n'
                'find "$MOD_UPDATE_PATH/system" -type d -exec chmod 755 {} +\n'
                'find "$MOD_UPDATE_PATH/system" -type f -exec chmod 644 {} +\n'
                'find "$MOD_UPDATE_PATH/system" -type f -exec chown root:root {} +\n'
                "log \"Copied system/ to MOD_UPDATE_PATH\"\n"
                'if [ -f "$BASE/service.sh" ]; then\n'
                '    cp -dr --preserve=all "$BASE/service.sh" "$MOD_UPDATE_PATH"\n'
                '    chown root:root "$MOD_UPDATE_PATH/service.sh"\n'
                '    chmod 755 "$MOD_UPDATE_PATH/service.sh"\n'
                "    log \"Copied service.sh to MOD_UPDATE_PATH\"\n"
                'fi\n'
                'if [ -d "$BASE/permissions" ]; then\n'
                '    cp -dr --preserve=all "$BASE/permissions" "$MOD_UPDATE_PATH"\n'
                '    find "$MOD_UPDATE_PATH/permissions" -type f -exec chmod 644 {} +\n'
                '    find "$MOD_UPDATE_PATH/permissions" -type f -exec chown root:root {} +\n'
                "    log \"Copied permissions/ to MOD_UPDATE_PATH\"\n"
                'fi\n'
                "log \"=== post-fs-data.sh end ===\"\n"
            )
            with open(os.path.join(LSP_TEMP, "post-fs-data.sh"), "w", newline="") as f:
                f.write(post_fs_data)
            _debug("  Injected post-fs-data.sh with logging")

            service_sh = (
                "#!/system/bin/sh\n"
                "LOGFILE=\"$(dirname \"$0\")/service.log\"\n"
                "log() { echo \"[$(date '+%Y-%m-%d %H:%M:%S')] $1\" | tee -a \"$LOGFILE\"; }\n"
                "log \"=== service.sh start ===\"\n"
                "MODDIR=${0%/*}\n"
                "PERM_DIR=\"$MODDIR/permissions\"\n"
                "log \"MODDIR=$MODDIR\"\n"
                "log \"PERM_DIR=$PERM_DIR\"\n"
                "\n"
                "while [ \"$(getprop sys.boot_completed)\" != \"1\" ]; do sleep 1; done\n"
                "sleep 3\n"
                "log \"Boot completed, processing profiles...\"\n"
                "\n"
                "COUNT=0\n"
                "GRANTED=0\n"
                "ENABLED=0\n"
                "for profile in \"$PERM_DIR\"/*.json; do\n"
                "    [ -f \"$profile\" ] || continue\n"
                "    PKG=$(basename \"$profile\" .json)\n"
                "    COUNT=$((COUNT + 1))\n"
                "    log \"--- Processing: $PKG ---\"\n"
                "\n"
                "    if ! pm list packages 2>/dev/null | grep -q \"package:$PKG\"; then\n"
                "        log \"SKIP: $PKG not installed\"\n"
                "        continue\n"
                "    fi\n"
                "    log \"FOUND: $PKG is installed\"\n"
                "\n"
                "    log \"Granting runtime permissions...\"\n"
                "    grep -o '\"android\\.[^\"]*\"' \"$profile\" | tr -d '\"' | while read perm; do\n"
                "        if pm grant \"$PKG\" \"$perm\" 2>/dev/null; then\n"
                "            log \"  GRANTED: $perm\"\n"
                "        else\n"
                "            log \"  SKIP: $perm (already granted or not applicable)\"\n"
                "        fi\n"
                "        GRANTED=$((GRANTED + 1))\n"
                "    done\n"
                "\n"
                "    if grep -q '\"hide_disable\": *true' \"$profile\"; then\n"
                "        if pm enable \"$PKG\" 2>/dev/null; then\n"
                "            log \"ENABLED: $PKG\"\n"
                "            ENABLED=$((ENABLED + 1))\n"
                "        else\n"
                "            log \"ENABLE SKIP: $PKG (already enabled)\"\n"
                "        fi\n"
                "    fi\n"
                "\n"
                "    if magisk resetprop -n \"persist.sys.priapp.$PKG\" \"1\" 2>/dev/null; then\n"
                "        log \"RESETPROP: persist.sys.priapp.$PKG=1\"\n"
                "    else\n"
                "        log \"RESETPROP SKIP: $PKG (magisk not available)\"\n"
                "    fi\n"
                "\n"
                "    log \"--- Done: $PKG ---\"\n"
                "done\n"
                "\n"
                "log \"Summary: profiles=$COUNT granted=$GRANTED enabled=$ENABLED\"\n"
                "log \"=== service.sh end ===\"\n"
            )
            with open(os.path.join(LSP_TEMP, "service.sh"), "w", newline="") as f:
                f.write(service_sh)
            _debug("  Injected service.sh with logging")

            for apk_path in apk_paths:
                pkg = ApkAnalyzer.get_package_name(apk_path)
                dest_dir = os.path.join(LSP_TEMP, "system", "priv-app", pkg)
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy2(apk_path, os.path.join(dest_dir, os.path.basename(apk_path)))
                _debug(f"  Added: system/priv-app/{pkg}/{os.path.basename(apk_path)}")

                profile = permission_profiles.get(pkg, {})
                if profile:
                    perm_dir = os.path.join(LSP_TEMP, "permissions")
                    os.makedirs(perm_dir, exist_ok=True)
                    with open(os.path.join(perm_dir, f"{pkg}.json"), "w", newline="") as f:
                        json.dump(profile, f, indent=2)
                    _debug(f"  Saved profile: permissions/{pkg}.json")

            # one merged XML per type: a block for EVERY package above
            InitrdManager.regenerate_permission_xmls(LSP_TEMP)

            image_path = os.path.join(INJECT_TEMP, LSP_IMAGE_NAME)
            result = subprocess.run(
                [IMG_CREATER, "-zlz4hc,9", image_path, LSP_TEMP],
                capture_output=True, text=True, timeout=60,
                creationflags=CREATE_NO_WINDOW)
            if result.returncode != 0:
                raise RuntimeError(f"img-creater failed: {result.stderr}")
            with open(image_path, "rb") as f:
                image_data = f.read()
            _debug(f"EROFS image: {len(image_data):,} bytes")
            return image_data
        finally:
            shutil.rmtree(LSP_TEMP, ignore_errors=True)

    def extract_lsp_image(self):
        _debug("extract_lsp_image()")
        data = CpioUtils.read_file(self.path, f"overlay.d/sbin/{LSP_IMAGE_NAME}")
        if not data:
            return None
        if os.path.exists(LSP_TEMP):
            shutil.rmtree(LSP_TEMP, ignore_errors=True)
        os.makedirs(LSP_TEMP, exist_ok=True)
        img_path = os.path.join(LSP_TEMP, LSP_IMAGE_NAME)
        with open(img_path, "wb") as f:
            f.write(data)
        extract_dir = os.path.join(LSP_TEMP, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        result = subprocess.run(
            [IMG_EXTRACTOR, f"--extract={extract_dir}", "--force", img_path],
            capture_output=True, text=True, timeout=60,
            creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            _debug(f"extract failed: {result.stderr}")
            shutil.rmtree(LSP_TEMP, ignore_errors=True)
            return None
        return extract_dir

    def repack_lsp_image(self):
        _debug("repack_lsp_image()")
        extract_dir = os.path.join(LSP_TEMP, "extracted")
        try:
            image_path = os.path.join(INJECT_TEMP, LSP_IMAGE_NAME)
            result = subprocess.run(
                [IMG_CREATER, "-zlz4hc,9", image_path, extract_dir],
                capture_output=True, text=True, timeout=60,
                creationflags=CREATE_NO_WINDOW)
            if result.returncode != 0:
                raise RuntimeError(f"img-creater failed: {result.stderr}")
            with open(image_path, "rb") as f:
                image_data = f.read()
            arcname = f"overlay.d/sbin/{LSP_IMAGE_NAME}"
            if CpioUtils.has_file(self.path, arcname):
                CpioUtils.delete_file(self.path, arcname)
            CpioUtils.add_file(self.path, arcname, image_data)
            _log(f"Repacked {LSP_IMAGE_NAME} ({len(image_data):,} bytes)")
            return True
        except PermissionError:
            _debug("File locked, using temp copy approach")
            return self._repack_lsp_image_via_temp(extract_dir)
        finally:
            shutil.rmtree(LSP_TEMP, ignore_errors=True)

    def _repack_lsp_image_via_temp(self, extract_dir):
        import tempfile
        image_path = os.path.join(INJECT_TEMP, LSP_IMAGE_NAME)
        result = subprocess.run(
            [IMG_CREATER, "-zlz4hc,9", image_path, extract_dir],
            capture_output=True, text=True, timeout=60,
            creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            raise RuntimeError(f"img-creater failed: {result.stderr}")
        with open(image_path, "rb") as f:
            image_data = f.read()
        arcname = f"overlay.d/sbin/{LSP_IMAGE_NAME}"
        tmp_initrd = tempfile.mktemp(suffix=".img")
        shutil.copy2(self.path, tmp_initrd)
        if CpioUtils.has_file(tmp_initrd, arcname):
            CpioUtils.delete_file(tmp_initrd, arcname)
        CpioUtils.add_file(tmp_initrd, arcname, image_data)
        def _do_replace():
            try:
                os.remove(self.path)
            except PermissionError:
                if WSADetector.is_running():
                    KillWSA.kill_all()
                    time.sleep(3)
                os.remove(self.path)
            shutil.copy2(tmp_initrd, self.path)
        CpioUtils._write_with_retry(_do_replace)
        try:
            os.remove(tmp_initrd)
        except Exception:
            pass
        _log(f"Repacked {LSP_IMAGE_NAME} ({len(image_data):,} bytes)")
        return True

    def inject_uninstall_txt(self, packages):
        content = "\n".join(packages) + "\n"
        arcname = "overlay.d/sbin/uninstall.txt"
        CpioUtils.delete_file(self.path, arcname)
        CpioUtils.add_file(self.path, arcname, content.encode("utf-8"))
        _log(f"Injected uninstall.txt ({len(packages)} packages)")

    def patch_postfsdata_uninstall(self):
        arcname = "overlay.d/sbin/post-fs-data.sh"

        user_log_block = ""
        if LOG_FOR_USER:
            user_log_block = (
                "    mkdir -p '/storage/emulated/0/WSA Installer'\n"
                '    USER_LOG="/storage/emulated/0/WSA Installer/post-fs-data.log"\n'
                '    cp -f "$EARLY_LOG" "$USER_LOG" 2>/dev/null\n'
            )

        root_transition = (
            '    printf "[%s] [Root] Android boot complete, copying log to user path and starting uninstallation\\n" "$(date \'+%Y-%m-%d %H:%M:%S\')" >> "$EARLY_LOG"\n'
        )
        if LOG_FOR_USER:
            root_transition += (
                '    printf "[%s] [Root] Android boot complete, copying log to user path and starting uninstallation\\n" "$(date \'+%Y-%m-%d %H:%M:%S\')" >> "$USER_LOG"\n'
            )

        log_fn = (
            '    log_uninstall() {\n'
            '        printf "[%s] [User] %s\\n" "$(date \'+%Y-%m-%d %H:%M:%S\')" "$1" >> "$EARLY_LOG"\n'
        )
        if LOG_FOR_USER:
            log_fn += '        printf "[%s] [User] %s\\n" "$(date \'+%Y-%m-%d %H:%M:%S\')" "$1" >> "$USER_LOG"\n'
        log_fn += "    }\n"

        uninstall_block = (
            "# --- TWRP uninstall handler (background) ---\n"
            "(\n"
            '    while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 1; done\n'
            "    sleep 5\n"
            '    EARLY_LOG="$(dirname "$0")/post-fs-data.log"\n'
            + user_log_block
            + root_transition
            + log_fn
            + '    UNINSTALL_FILE="$(dirname "$0")/uninstall.txt"\n'
            '    if [ -f "$UNINSTALL_FILE" ]; then\n'
            '        log_uninstall "=== TWRP Uninstall start ==="\n'
            "        while IFS= read -r PKG; do\n"
            '            [ -z "$PKG" ] && continue\n'
            '            log_uninstall "UNINSTALL: $PKG"\n'
            '            if pm uninstall "$PKG" 2>/dev/null; then\n'
            '                log_uninstall "  UNINSTALLED: $PKG"\n'
            "            else\n"
            '                log_uninstall "  FAILED: $PKG"\n'
            "            fi\n"
            "        done < \"$UNINSTALL_FILE\"\n"
            "        rm -f \"$UNINSTALL_FILE\"\n"
            '        log_uninstall "=== TWRP Uninstall complete ==="\n'
            "    fi\n"
            ") &\n"
            "# --- end TWRP uninstall handler ---\n"
        )

        full_script = (
            "#!/bin/sh\n"
            'LOGFILE="$(dirname "$0")/post-fs-data.log"\n'
            'log() { printf "[%s] [Root] %s\\n" "$(date \'+%Y-%m-%d %H:%M:%S\')" "$1" >> "$LOGFILE"; }\n'
            'log "=== post-fs-data.sh start ==="\n'
            "MAGISKTMP=/sbin\n"
            "[ -d /sbin ] || MAGISKTMP=/debug_ramdisk\n"
            'log "MAGISKTMP=$MAGISKTMP"\n'
            "MAGISKBIN=/data/adb/magisk\n"
            "if [ ! -d /data/adb ]; then\n"
            "    mkdir -m 700 /data/adb\n"
            '    chcon u:object_r:adb_data_file:s0 /data/adb\n'
            '    log "Created /data/adb"\n'
            "fi\n"
            "if [ ! -d $MAGISKBIN ]; then\n"
            "    mkdir -p -m 755 $MAGISKBIN\n"
            '    chcon u:object_r:system_file:s0 $MAGISKBIN\n'
            '    log "Created $MAGISKBIN"\n'
            "fi\n"
            "ABI=$(getprop ro.product.cpu.abi)\n"
            'log "ABI=$ABI"\n'
            "for file in busybox magiskpolicy magiskboot magiskinit; do\n"
            '    [ -x "$MAGISKBIN/$file" ] || {\n'
            '        unzip -d $MAGISKBIN -oj $MAGISKTMP/stub.apk "lib/$ABI/lib$file.so"\n'
            '        mv $MAGISKBIN/lib$file.so $MAGISKBIN/$file\n'
            '        chmod 755 "$MAGISKBIN/$file"\n'
            '        log "Extracted $file"\n'
            "    }\n"
            "done\n"
            "for file in util_functions.sh boot_patch.sh; do\n"
            '    [ -x "$MAGISKBIN/$file" ] || {\n'
            '        unzip -d $MAGISKBIN -oj $MAGISKTMP/stub.apk "assets/$file"\n'
            '        chmod 755 "$MAGISKBIN/$file"\n'
            '        log "Extracted $file"\n'
            "    }\n"
            "done\n"
            'for file in "$MAGISKTMP"/*; do\n'
            '    if echo "$file" | grep -Eq "lsp_.+\\.img"; then\n'
            '        foldername=$(basename "$file" .img)\n'
            '        mkdir -p "$MAGISKTMP/$foldername"\n'
            '        mount -t auto -o ro,loop "$file" "$MAGISKTMP/$foldername"\n'
            '        log "Mounted $file -> $MAGISKTMP/$foldername"\n'
            '        "$MAGISKTMP/$foldername/post-fs-data.sh" &\n'
            "    fi\n"
            "done\n"
            "wait\n"
            'log "All post-fs-data.sh scripts completed"\n'
            'for file in "$MAGISKTMP"/*; do\n'
            '    if echo "$file" | grep -Eq "lsp_.+\\.img"; then\n'
            '        foldername=$(basename "$file" .img)\n'
            '        umount "$MAGISKTMP/$foldername"\n'
            '        log "Unmounted $MAGISKTMP/$foldername"\n'
            '        rm -rf "${MAGISKTMP:?}/${foldername:?}"\n'
            '        rm -f "$file"\n'
            "    fi\n"
            "done\n"
            'log "Cleanup complete"\n'
            'log "=== post-fs-data.sh end ==="\n'
            "\n"
            + uninstall_block
        )

        CpioUtils.delete_file(self.path, arcname)
        CpioUtils.add_file(self.path, arcname, full_script.encode("utf-8"))
        _log("Replaced post-fs-data.sh with full version + uninstall handler")
        return True

    def find_existing_apks(self):
        _debug("find_existing_apks()")
        extract_dir = self.extract_lsp_image()
        if not extract_dir:
            return []
        result = []
        priv_app = os.path.join(extract_dir, "system", "priv-app")
        if os.path.isdir(priv_app):
            for pkg_dir in os.listdir(priv_app):
                pkg_path = os.path.join(priv_app, pkg_dir)
                if os.path.isdir(pkg_path):
                    for apk in os.listdir(pkg_path):
                        if apk.endswith(".apk"):
                            result.append((pkg_dir, os.path.join(pkg_path, apk)))
        shutil.rmtree(LSP_TEMP, ignore_errors=True)
        _debug(f"find_existing_apks: {result}")
        return result

    def list_tree(self):
        """[(name, mode, size)] for every entry, for the IMG Manager tree."""
        _debug("list_tree()")
        return CpioUtils.list_entries(self.path)

    def overwrite(self, arcname, file_data, mode=None):
        _debug(f"overwrite({arcname})")
        CpioUtils.overwrite_file(self.path, arcname, file_data, mode=mode)

    def delete_entries(self, names):
        _debug(f"delete_entries({len(names)})")
        removed = 0
        for name in names:
            removed += CpioUtils.delete_tree(self.path, name)
        _log(f"Deleted {removed} entries")
        return removed

    def rename(self, old, new):
        _debug(f"rename({old} -> {new})")
        CpioUtils.rename_entry(self.path, old, new)
        _log(f"Renamed {old} -> {new}")

    def extract(self, dest_dir, names=None):
        _debug(f"extract({dest_dir}, names={names})")
        count = CpioUtils.extract_to(self.path, dest_dir, names)
        _log(f"Extracted {count} entries to {dest_dir}")
        return count

    def new_folder(self, arcname):
        arcname = arcname.strip("/")
        _debug(f"new_folder({arcname})")
        if CpioUtils.has_file(self.path, arcname):
            raise ValueError(f"already exists: {arcname}")
        dirs = CpioUtils.parent_dirs(arcname) + [arcname]
        CpioUtils.ensure_dir_entries(self.path, sorted(set(dirs)), 0o040755)
        _log(f"Created folder {arcname}")


class WSADetector:

    @staticmethod
    def is_installed():
        _debug("WSADetector.is_installed()")
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 "Get-AppxPackage *WindowsSubsystemForAndroid* "
                 "| Select-Object -ExpandProperty PackageFamilyName"],
                capture_output=True, text=True,
                creationflags=CREATE_NO_WINDOW, timeout=10)
            return "WindowsSubsystemForAndroid" in (r.stdout or "").strip()
        except Exception:
            return False

    @staticmethod
    def find_path():
        _debug("WSADetector.find_path()")
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 "Get-AppxPackage *WindowsSubsystemForAndroid* "
                 "| Select-Object -ExpandProperty InstallLocation"],
                capture_output=True, text=True,
                creationflags=CREATE_NO_WINDOW, timeout=10)
            loc = (r.stdout or "").strip()
            _debug(f"  PowerShell output: {loc}")
            if loc and os.path.isdir(loc) and WSADetector._validate(loc):
                _debug(f"  find_path() -> {loc}")
                return loc
        except Exception:
            pass
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            for sub in [
                os.path.join("Microsoft", "WindowsApps", WSA_FAMILY),
                WSA_FAMILY,
            ]:
                p = os.path.join(local, sub)
                if os.path.isdir(p) and WSADetector._validate(p):
                    _debug(f"  find_path() -> {p}")
                    return p
        _debug("  find_path() -> None")
        return None

    @staticmethod
    def _validate(path):
        required = [
            os.path.join("WsaClient", "WsaClient.exe"),
            os.path.join("Tools", "kernel"),
            "system.vhdx",
        ]
        result = all(os.path.exists(os.path.join(path, f)) for f in required)
        _debug(f"_validate({path}) -> {result}")
        return result

    @staticmethod
    def initrd_path(wsa_path):
        p = os.path.join(wsa_path, "Tools", "initrd.img")
        _debug(f"initrd_path() -> {p}")
        return p

    @staticmethod
    def is_running():
        _debug("WSADetector.is_running()")
        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq WsaClient.exe"],
                capture_output=True, text=True,
                creationflags=CREATE_NO_WINDOW, timeout=5)
            result = "WsaClient.exe" in r.stdout
            _debug(f"is_running() -> {result}")
            return result
        except Exception:
            _debug("is_running() -> False (exception)")
            return False

    @staticmethod
    def ensure_running():
        _debug("ensure_running()")
        for attempt in range(3):
            if WSADetector.is_running():
                return True
            try:
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command",
                     "Start-Process 'wsa://system'"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW, timeout=10)
            except Exception:
                pass
            time.sleep(12)
        return WSADetector.is_running()

    @staticmethod
    def check_root():
        _debug("WSADetector.check_root()")
        try:
            r = subprocess.run(
                ["adb", "shell", "su -c 'id'"],
                capture_output=True, text=True,
                creationflags=CREATE_NO_WINDOW, timeout=10)
            result = "uid=0" in r.stdout
            _debug(f"check_root() -> {result}")
            return result
        except Exception:
            _debug("check_root() -> False (exception)")
            return False


class KillWSA:

    @staticmethod
    def kill_all():
        _debug("KillWSA.kill_all()")
        try:
            subprocess.run(
                ["WsaClient.exe", "/shutdown"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW, timeout=5)
            _debug("  WsaClient.exe /shutdown sent")
        except Exception:
            _debug("  WsaClient.exe /shutdown failed")
            pass
        time.sleep(1)
        try:
            ps_cmd = (
                'Get-CimInstance Win32_Process | '
                'Where-Object { ($_.Name -match "powershell.exe" -or $_.Name -match "pwsh.exe") '
                '-and $_.CommandLine -match "Install.ps1" } | '
                'ForEach-Object { Stop-Process -Id $_.ProcessId -Force }'
            )
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW, timeout=10)
        except Exception:
            pass
        for target in ["WsaClient.exe", "WindowsSubsystemForAndroid.exe",
                       "adb.exe", "vmmemWSA.exe", "WsaService.exe",
                       "vmwp.exe", "vmconnect.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", target, "/T"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW, timeout=5)
                _debug(f"  taskkill {target} sent")
            except Exception:
                pass
        _debug("KillWSA.kill_all() waiting 5s...")
        time.sleep(5)

    @staticmethod
    def wait_file_free(file_path, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            try:
                with open(file_path, "rb") as f:
                    f.read(1)
                return True
            except (PermissionError, OSError):
                time.sleep(2)
        return False


class ADBManager:

    def __init__(self, device=None):
        self.device = device or ADB_DEVICE

    def _run(self, args, timeout=10):
        cmd = [ADB_PATH] + args
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=CREATE_NO_WINDOW, timeout=timeout)
            return r.stdout or ""
        except Exception:
            return ""

    def is_recovery(self):
        output = self._run(["devices"])
        return f"{self.device}\trecovery" in output

    def connect_and_check_recovery(self):
        if not os.path.exists(ADB_PATH):
            return False
        self._run(["connect", self.device])
        time.sleep(2)
        output = self._run(["devices"])
        return f"{self.device}\trecovery" in output

    def wait_for_recovery(self):
        while True:
            try:
                self._run(["connect", self.device])
                output = self._run(["devices"])
                if f"{self.device}\trecovery" in output:
                    return True
            except Exception:
                pass
            time.sleep(2)


class RecoverySignals(QObject):
    log_updated = Signal(str)
    close_requested = Signal()
    progress_updated = Signal(float)


class RecoveryWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._drag_offset = None
        self._logo = QPixmap(str(LOGO_PATH))
        self._status_text = "Starting..."
        self._bottom_text = "Starting Window Subsystem For Android\u2122 Into Twrp Recovery"
        self._progress_value = 0.0
        self._show_progress_fill = True
        self._signals = RecoverySignals()
        self._signals.log_updated.connect(self._on_log_update)
        self._signals.close_requested.connect(self.close)
        self._signals.progress_updated.connect(self._on_progress_update)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_progress)
        self._anim_timer.start(50)

    def _on_log_update(self, msg):
        self._status_text = msg
        self.update()

    def _on_progress_update(self, value):
        self._progress_value = value
        self.update()

    def _animate_progress(self):
        self._progress_value += 0.02
        if self._progress_value > 1.0:
            self._progress_value = 0.0
        self.update()

    def update_log(self, msg):
        self._signals.log_updated.emit(msg)

    def request_close(self):
        self._signals.close_requested.emit()

    def _window_path(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(1.5, 1.5, REFERENCE_WIDTH - 3, REFERENCE_HEIGHT - 3),
                            WINDOW_RADIUS, WINDOW_RADIUS)
        return path

    def _header_path(self):
        r = WINDOW_RADIUS
        right = REFERENCE_WIDTH - 1.5
        bottom = HEADER_HEIGHT
        left = 1.5
        top = 1.5
        path = QPainterPath()
        path.moveTo(left + r, top)
        path.lineTo(right - r, top)
        path.quadTo(right, top, right, top + r)
        path.lineTo(right, bottom)
        path.lineTo(left, bottom)
        path.lineTo(left, top + r)
        path.quadTo(left, top, left + r, top)
        path.closeSubpath()
        return path

    @staticmethod
    def _font(size, weight=QFont.Normal):
        font = QFont("Segoe UI")
        font.setPixelSize(size)
        font.setWeight(weight)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font

    def paintEvent(self, _event):
        painter = QPainter(self)
        sx = self.width() / REFERENCE_WIDTH
        sy = self.height() / REFERENCE_HEIGHT
        painter.scale(sx, sy)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        outer = self._window_path()
        painter.fillPath(outer, MAIN_COLOR)
        painter.fillPath(self._header_path(), HEADER_COLOR)

        if not self._logo.isNull():
            painter.drawPixmap(LOGO_RECT, self._logo, QRectF(self._logo.rect()))
            painter.drawPixmap(ICON_RECT, self._logo, QRectF(self._logo.rect()))

        painter.setPen(TITLE_COLOR)
        painter.setFont(self._font(TITLE_FONT_SIZE))
        painter.drawText(TITLE_RECT, Qt.AlignLeft | Qt.AlignVCenter, APP_NAME)

        pen = QPen(QColor(232, 232, 232), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        cx, cy = CLOSE_CENTER.x(), CLOSE_CENTER.y()
        painter.drawLine(cx - CLOSE_HALF, cy - CLOSE_HALF, cx + CLOSE_HALF, cy + CLOSE_HALF)
        painter.drawLine(cx + CLOSE_HALF, cy - CLOSE_HALF, cx - CLOSE_HALF, cy + CLOSE_HALF)

        progress_w = int(REFERENCE_WIDTH * 0.35)
        progress_x = (REFERENCE_WIDTH - progress_w) // 2
        progress_y = 831
        progress_h = 8
        painter.setPen(Qt.NoPen)
        painter.setBrush(PROGRESS_TRACK)
        painter.drawRoundedRect(QRectF(progress_x, progress_y, progress_w, progress_h), 4, 4)

        if self._show_progress_fill:
            fill_w = progress_w * self._progress_value
            fill_rect = QRectF(progress_x, progress_y, fill_w, progress_h)
            painter.setBrush(PROGRESS_FILL)
            painter.drawRoundedRect(fill_rect, 4, 4)

        status_font_size = max(18, int(REFERENCE_WIDTH * 0.018))
        painter.setPen(TEXT_COLOR)
        painter.setFont(self._font(status_font_size))
        status_rect = QRectF(0, progress_y + progress_h + 10,
                             REFERENCE_WIDTH, status_font_size + 20)
        painter.drawText(status_rect, Qt.AlignHCenter | Qt.AlignTop, self._status_text)

        bottom_font_size = max(20, int(REFERENCE_WIDTH * 0.018))
        bottom_rect = QRectF(60, 1020, REFERENCE_WIDTH - 120, bottom_font_size + 20)
        painter.setFont(self._font(bottom_font_size))
        painter.drawText(bottom_rect, Qt.AlignLeft | Qt.AlignVCenter, self._bottom_text)

        border_pen = QPen(BORDER_COLOR, BORDER_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(outer)
        painter.end()

    def _reference_pos(self, event):
        sx = REFERENCE_WIDTH / WINDOW_WIDTH
        sy = REFERENCE_HEIGHT / WINDOW_HEIGHT
        pos = event.position()
        return QPoint(round(pos.x() * sx), round(pos.y() * sy))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            ref_pos = self._reference_pos(event)
            if (ref_pos - CLOSE_CENTER).manhattanLength() <= 28:
                self.close()
                return
            if ref_pos.y() <= HEADER_HEIGHT:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = None


class PermissionManagerSignals(QObject):
    # object, not dict: the cancel/close path emits None and Signal(dict) would
    # reject it (Shiboken conversion error), delivering {} instead of None.
    result_ready = Signal(object)


class PermissionManagerWindow(QWidget):

    PM_W = 640
    PM_H = 500
    PM_HDR_H = 44
    PM_RADIUS = 16
    ROW_H = 28
    LOCK_W = 24
    PERM_BOX_H = 240

    def __init__(self, package_name, app_label, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._package_name = package_name
        self._app_label = app_label
        self._signals = PermissionManagerSignals()
        self._result_emitted = False
        self._drag_offset = None
        self._hover_btn = None
        self._chk_hide_uninstall = True
        self._chk_hide_disable = True
        self._perm_checks = []
        self._scroll_y = 0
        seen = set()
        for perm in sorted(PRIVILEGED_PERMS):
            if perm in seen:
                continue
            seen.add(perm)
            self._perm_checks.append({"perm": perm, "checked": True, "locked": True, "greyed": False, "cat": "privileged"})
        for perm in DANGEROUS_PERMS:
            if perm in seen:
                continue
            seen.add(perm)
            self._perm_checks.append({"perm": perm, "checked": True, "locked": True, "greyed": False, "cat": "dangerous"})
        for perm in SPECIAL_PERMS:
            if perm in seen:
                continue
            seen.add(perm)
            self._perm_checks.append({"perm": perm, "checked": True, "locked": False, "greyed": False, "cat": "special"})
        for perm in NORMAL_PERMS:
            if perm in seen:
                continue
            seen.add(perm)
            self._perm_checks.append({"perm": perm, "checked": False, "locked": False, "greyed": True, "cat": "normal"})
        self._pm_h = self.PM_H
        self.setFixedSize(self.PM_W, self._pm_h)
        self._build_layout()

    def _build_layout(self):
        cx = self.PM_W - 10 - 24
        self._close_rect = (cx, 10, 24, 24)
        y = self.PM_HDR_H + 8
        self._app_label_y = y
        y += 32
        self._prot_label_y = y
        y += 22
        self._prot_box_y = y
        self._prot_chk1_y = y + 9
        self._prot_chk2_y = y + 9 + 30
        y += 30 * 2 + 18
        self._perm_label_y = y
        y += 24
        self._perm_box_y = y
        self._perm_content_y = y + 8
        self._perm_box_h = self.PERM_BOX_H
        btn_y = self._pm_h - 50
        self._btn_ok_rect = (self.PM_W // 2 - 130, btn_y, 120, 36)
        self._btn_cancel_rect = (self.PM_W // 2 + 10, btn_y, 120, 36)

    def _max_scroll(self):
        content_h = len(self._perm_checks) * self.ROW_H + 16
        return max(0, content_h - self._perm_box_h)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self._scroll_y -= delta // 3
        self._scroll_y = max(0, min(self._scroll_y, self._max_scroll()))
        self.update()

    def _on_ok(self):
        self._result_emitted = True
        self._signals.result_ready.emit(self.get_result())
        self.close()

    def _on_cancel(self):
        self._result_emitted = True
        self._signals.result_ready.emit(None)
        self.close()

    def closeEvent(self, event):
        # Alt+F4 / any close that is not OK/Cancel must not leave the caller's
        # QEventLoop spinning forever - emit the cancelled result once.
        if not self._result_emitted:
            self._result_emitted = True
            self._signals.result_ready.emit(None)
        super().closeEvent(event)

    def get_result(self):
        return {
            "hide_uninstall": self._chk_hide_uninstall,
            "hide_disable": self._chk_hide_disable,
            "privapp_perms": [it["perm"] for it in self._perm_checks if it["checked"] and it["cat"] == "privileged"],
            "runtime_perms": [it["perm"] for it in self._perm_checks if it["checked"] and it["cat"] in ("dangerous", "special")],
            "fixed_runtime_perms": [it["perm"] for it in self._perm_checks if it["checked"] and it["locked"] and it["cat"] in ("dangerous", "special")],
        }

    @staticmethod
    def _font(size, weight=QFont.Normal):
        font = QFont("Segoe UI")
        font.setPixelSize(size)
        font.setWeight(weight)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font

    def _window_path(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(1.5, 1.5, self.PM_W - 3, self._pm_h - 3),
                            self.PM_RADIUS, self.PM_RADIUS)
        return path

    def _header_path(self):
        r = self.PM_RADIUS
        right = self.PM_W - 1.5
        bottom = self.PM_HDR_H
        left = 1.5
        top = 1.5
        path = QPainterPath()
        path.moveTo(left + r, top)
        path.lineTo(right - r, top)
        path.quadTo(right, top, right, top + r)
        path.lineTo(right, bottom)
        path.lineTo(left, bottom)
        path.lineTo(left, top + r)
        path.quadTo(left, top, left + r, top)
        path.closeSubpath()
        return path

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        outer = self._window_path()
        p.fillPath(outer, MAIN_COLOR)
        p.fillPath(self._header_path(), HEADER_COLOR)
        p.setPen(TITLE_COLOR)
        p.setFont(self._font(14))
        p.drawText(QRectF(14, 8, 200, 28), Qt.AlignLeft | Qt.AlignVCenter, "Permission Manager")
        pen = QPen(QColor(232, 232, 232), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        cx = self.PM_W - 22
        p.drawLine(cx, 14, cx + 10, 24)
        p.drawLine(cx + 10, 14, cx, 24)
        p.setPen(TEXT_COLOR)
        p.setFont(self._font(13, QFont.Bold))
        p.drawText(QRectF(14, self._app_label_y, self.PM_W - 28, 28),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   f"{self._app_label} ({self._package_name})")
        p.setPen(QColor(160, 160, 160))
        p.setFont(self._font(11))
        p.drawText(QRectF(14, self._prot_label_y, self.PM_W - 28, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, "App Protection")
        p.setPen(BORDER_COLOR)
        p.drawRoundedRect(QRectF(10, self._prot_box_y, self.PM_W - 20, 70), 6, 6)
        self._draw_chk(p, 20, self._prot_chk1_y, self._chk_hide_disable, "Hide Disable")
        self._draw_chk(p, 20, self._prot_chk2_y, self._chk_hide_uninstall, "Hide Uninstall")
        total = len(self._perm_checks)
        p.setPen(QColor(160, 160, 160))
        p.setFont(self._font(11))
        p.drawText(QRectF(14, self._perm_label_y, self.PM_W - 28, 20),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   f"Permissions ({total})")
        p.setPen(BORDER_COLOR)
        p.drawRoundedRect(QRectF(10, self._perm_box_y, self.PM_W - 20, self._perm_box_h), 6, 6)
        p.setClipRect(QRectF(14, self._perm_box_y + 4, self.PM_W - 28, self._perm_box_h - 8))
        row_h = self.ROW_H
        for i, item in enumerate(self._perm_checks):
            cy = self._perm_content_y + i * row_h - self._scroll_y
            if item["greyed"]:
                p.setPen(QColor(100, 100, 100))
                p.setFont(self._font(11))
                p.drawText(QRectF(44, cy, self.PM_W - 120, 16),
                           Qt.AlignLeft | Qt.AlignVCenter, item["perm"])
                p.setPen(QColor(80, 80, 80))
                p.setFont(self._font(9))
                p.drawText(QRectF(self.PM_W - 70, cy + 2, 50, 16),
                           Qt.AlignRight | Qt.AlignVCenter, "auto")
            else:
                self._draw_square_chk(p, 20, cy, item["checked"], item["perm"])
                if item["checked"]:
                    lock_x = self.PM_W - 60
                    lock_y = cy
                    self._draw_lock(p, lock_x, lock_y, item["locked"])
        p.setClipping(False)
        self._draw_btn(p, self._btn_ok_rect, "Install", True)
        self._draw_btn(p, self._btn_cancel_rect, "Cancel", False)
        border_pen = QPen(BORDER_COLOR, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(border_pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(outer)
        p.end()

    def _draw_square_chk(self, p, x, y, checked, text):
        p.save()
        sz = 16
        if checked:
            p.setBrush(PROGRESS_FILL)
            p.setPen(PROGRESS_FILL)
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(120, 120, 120))
        p.drawRoundedRect(QRectF(x, y, sz, sz), 3, 3)
        if checked:
            p.setPen(QColor(255, 255, 255))
            p.setFont(self._font(10, QFont.Bold))
            p.drawText(QRectF(x, y, sz, sz), Qt.AlignCenter, "\u2713")
        p.setPen(TEXT_COLOR)
        p.setFont(self._font(11))
        p.drawText(QRectF(x + sz + 6, y, self.PM_W - x - sz - 80, sz),
                   Qt.AlignLeft | Qt.AlignVCenter, text)
        p.restore()

    def _draw_lock(self, p, x, y, locked):
        p.save()
        sz = self.LOCK_W
        if locked:
            p.setPen(QColor(255, 180, 0))
            p.setFont(self._font(14))
            p.drawText(QRectF(x, y, sz, sz), Qt.AlignCenter, "\U0001f512")
        else:
            p.setPen(QColor(120, 120, 120))
            p.setFont(self._font(14))
            p.drawText(QRectF(x, y, sz, sz), Qt.AlignCenter, "\U0001f513")
        p.restore()

    def _draw_chk(self, p, x, y, checked, text):
        p.save()
        sz = 18
        if checked:
            p.setBrush(PROGRESS_FILL)
            p.setPen(PROGRESS_FILL)
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(120, 120, 120))
        p.drawRoundedRect(QRectF(x, y, sz, sz), 3, 3)
        if checked:
            p.setPen(QColor(255, 255, 255))
            p.setFont(self._font(11, QFont.Bold))
            p.drawText(QRectF(x, y, sz, sz), Qt.AlignCenter, "\u2713")
        p.setPen(TEXT_COLOR)
        p.setFont(self._font(11))
        p.drawText(QRectF(x + sz + 6, y, 500, sz),
                   Qt.AlignLeft | Qt.AlignVCenter, text)
        p.restore()

    def _draw_btn(self, p, rect, text, is_ok):
        x, y, w, h = rect
        is_h = self._hover_btn == ("ok" if is_ok else "cancel")
        p.save()
        if is_ok:
            if is_h:
                p.setBrush(QColor(180, 70, 220))
            else:
                p.setBrush(PROGRESS_FILL)
            p.setPen(Qt.NoPen)
        else:
            if is_h:
                p.setBrush(QColor(50, 50, 50))
            else:
                p.setBrush(Qt.NoBrush)
            p.setPen(BORDER_COLOR)
        p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)
        p.setPen(QColor(255, 255, 255) if is_ok else TEXT_COLOR)
        p.setFont(self._font(12, QFont.Bold))
        p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, text)
        p.restore()

    def _hit_test(self, ref):
        cx, cy, cw, ch = self._close_rect
        if cx <= ref.x() <= cx + cw and cy <= ref.y() <= cy + ch:
            return "close"
        bx, by, bw, bh = self._btn_ok_rect
        if bx <= ref.x() <= bx + bw and by <= ref.y() <= by + bh:
            return "ok"
        bx, by, bw, bh = self._btn_cancel_rect
        if bx <= ref.x() <= bx + bw and by <= ref.y() <= by + bh:
            return "cancel"
        bx, by = 20, self._prot_chk1_y
        if bx <= ref.x() <= bx + 500 and by <= ref.y() <= by + 20:
            return "prot_disable"
        by2 = self._prot_chk2_y
        if bx <= ref.x() <= bx + 500 and by2 <= ref.y() <= by2 + 20:
            return "prot_uninstall"
        for i in range(len(self._perm_checks)):
            px = 20
            py = self._perm_content_y + i * self.ROW_H - self._scroll_y
            lock_x = self.PM_W - 60
            if lock_x <= ref.x() <= lock_x + self.LOCK_W and py <= ref.y() <= py + self.ROW_H:
                if not self._perm_checks[i]["greyed"] and self._perm_checks[i]["checked"]:
                    return f"lock_{i}"
            if px <= ref.x() <= px + 500 and py <= ref.y() <= py + 20:
                return f"perm_{i}"
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        sx = self.PM_W / self.width()
        sy = self._pm_h / self.height()
        pos = event.position()
        ref = QPoint(round(pos.x() * sx), round(pos.y() * sy))
        hit = self._hit_test(ref)
        if hit == "close":
            self._on_cancel()
        elif hit == "ok":
            self._on_ok()
        elif hit == "cancel":
            self._on_cancel()
        elif hit and hit.startswith("perm_"):
            idx = int(hit.split("_")[1])
            item = self._perm_checks[idx]
            if not item["greyed"]:
                item["checked"] = not item["checked"]
                self.update()
        elif hit and hit.startswith("lock_"):
            idx = int(hit.split("_")[1])
            item = self._perm_checks[idx]
            item["locked"] = not item["locked"]
            self.update()
        elif hit and hit.startswith("prot_"):
            tag = hit.split("_")[1]
            if tag == "uninstall":
                self._chk_hide_uninstall = not self._chk_hide_uninstall
            elif tag == "disable":
                self._chk_hide_disable = not self._chk_hide_disable
            self.update()
        elif ref.y() <= self.PM_HDR_H:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        sx = self.PM_W / self.width()
        sy = self._pm_h / self.height()
        pos = event.position()
        ref = QPoint(round(pos.x() * sx), round(pos.y() * sy))
        hit = self._hit_test(ref)
        new_hover = None
        if hit in ("ok", "cancel"):
            new_hover = hit
        if new_hover != self._hover_btn:
            self._hover_btn = new_hover
            self.update()
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = None


class ScriptEditorDialog(QDialog):
    """In-app text editor for scripts stored inside the image."""

    _STYLE = """
        QDialog { background: #171a21; color: #e6e9ef; }
        QLabel { background: transparent; color: #8a93a6; font-size: 11px; }
        QPlainTextEdit {
            background: #12151c; color: #e6e9ef;
            border: 1px solid #2b3242; border-radius: 6px;
            selection-background-color: #2f5f9e; selection-color: #ffffff;
        }
        QPushButton {
            background: #232838; color: #e6e9ef;
            border: 1px solid #3a4150; border-radius: 5px;
            padding: 5px 16px; font-size: 12px;
        }
        QPushButton:hover { background: #2c3346; border-color: #5a6478; }
    """

    def __init__(self, arcname, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit \u2014 {arcname}")
        self.setStyleSheet(self._STYLE)
        self.resize(780, 560)
        self.setMinimumSize(520, 360)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        outer.addWidget(QLabel(f"/{arcname}   \u00b7   saving writes to the staged image"))

        self._edit = QPlainTextEdit()
        self._edit.setPlainText(data.decode("utf-8", errors="replace"))
        editor_font = QFont("Consolas")
        editor_font.setPixelSize(13)
        self._edit.setFont(editor_font)
        self._edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        outer.addWidget(self._edit, 1)

        self._status = QLabel("")
        outer.addWidget(self._status)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setStyleSheet("""
            QPushButton {
                background: #1558b0; color: #ffffff;
                border: 1px solid #2f7ad6; border-radius: 5px;
                padding: 5px 16px; font-weight: bold;
            }
            QPushButton:hover { background: #1a67ca; }
        """)
        save.setDefault(True)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(save)
        outer.addLayout(row)

        self._edit.textChanged.connect(self._update_status)
        self._update_status()

    def _update_status(self):
        text = self._edit.toPlainText()
        self._status.setText(
            f"{text.count(chr(10)) + 1} lines \u00b7 {len(text)} chars")

    def result_bytes(self):
        return self._edit.toPlainText().encode("utf-8")


class ArchiveViewerDialog(QDialog):
    """Browse an archive that lives inside the image without leaving the app.

    Understands cpio (native), gzip/xz/bz2 (stdlib) including when they wrap
    a cpio or tar, plus zip, tar and 7z through the bundled 7z.exe.
    """

    _STYLE = """
        QDialog { background: #171a21; color: #e6e9ef; }
        QLabel { background: transparent; color: #8a93a6; font-size: 11px; }
        QTreeWidget {
            background: #12151c; alternate-background-color: #171b24;
            color: #e6e9ef; border: 1px solid #2b3242;
            border-radius: 6px; outline: 0; font-size: 12px;
        }
        QTreeWidget::item { padding: 2px 4px; }
        QTreeWidget::item:selected { background: #2f5f9e; color: #ffffff; }
        QHeaderView::section {
            background: #1c2130; color: #aab2c5;
            border: none; border-right: 1px solid #2b3242;
            border-bottom: 1px solid #2b3242;
            padding: 4px 6px; font-size: 11px;
        }
        QPushButton {
            background: #232838; color: #e6e9ef;
            border: 1px solid #3a4150; border-radius: 5px;
            padding: 5px 16px; font-size: 12px;
        }
        QPushButton:hover { background: #2c3346; border-color: #5a6478; }
        QPushButton:disabled { background: #1a1e27; color: #5b6272; border-color: #262b36; }
    """

    _DEPTH_LIMIT = 4

    @staticmethod
    def sniff(data, name=""):
        """Format tag for `data` from its MAGIC ONLY, or None.

        The file name is deliberately ignored: trusting an extension fed
        non-xz bytes to lzma, which raised "Input format not supported by
        decoder" on entries 7-Zip opened fine.
        """
        if not data:
            return None
        if data[:6] in (b"070701", b"070702", b"070707"):
            return "cpio"
        if data[:2] == b"\x1f\x8b":
            return "gzip"
        if data[:6] == b"\xfd7zXZ\x00":
            return "xz"
        if data[:3] == b"BZh":
            return "bz2"
        if data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
            return "zip"
        if data[:6] == b"7z\xbc\xaf\x27\x1c":
            return "7z"
        if data[:4] == b"\x04\x22\x4d\x18":
            return "lz4"
        if data[:4] == b"\x28\xb5\x2f\xfd":
            return "zstd"
        if data[257:262] == b"ustar":
            return "tar"
        return None

    def __init__(self, arcname, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Archive \u2014 {arcname}")
        self.setStyleSheet(self._STYLE)
        self.resize(820, 560)
        self.setMinimumSize(520, 360)

        self._arcname = arcname
        self._entries = []
        self._extract = None
        self._error = None
        self._used_7z = False
        self._temp_files = []
        self._keepalive = None
        # compression wrappers peeled off outermost-first ("gz", "xz", ...)
        # and the inner container we can rebuild ("cpio" / "zip" / "tar")
        self._layers = []
        self._container = None
        # arcname -> original cpio/zip/tar mode, so untouched entries keep
        # their permission bits and symlinks survive the round trip
        self._modes = {}
        self._packed = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        self._header = QLabel("")
        outer.addWidget(self._header)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Name", "Size", "Type"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # multi-select: Ctrl/Shift to pick, Ctrl+A to take everything
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_menu)
        hdr = self._tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        outer.addWidget(self._tree, 1)

        row = QHBoxLayout()
        self._hint = QLabel(
            "Read-only preview \u00b7 extraction writes outside the image")
        row.addWidget(self._hint)
        row.addStretch(1)
        close_btn = QPushButton("Close")
        self._extract_sel_btn = QPushButton("Extract selected\u2026")
        self._extract_all_btn = QPushButton("Extract all\u2026")
        self._extract_btn = self._extract_all_btn
        self._edit_btn = QPushButton("Edit\u2026")
        for btn in (self._extract_sel_btn, self._extract_all_btn, self._edit_btn):
            btn.setStyleSheet("""
                QPushButton {
                    background: #1558b0; color: #ffffff;
                    border: 1px solid #2f7ad6; border-radius: 5px;
                    padding: 5px 16px; font-weight: bold;
                }
                QPushButton:hover { background: #1a67ca; }
                QPushButton:disabled { background: #1a1e27; color: #5b6272; border-color: #262b36; }
            """)
        close_btn.clicked.connect(self.reject)
        self._extract_sel_btn.clicked.connect(
            lambda _checked=False: self._on_extract(True))
        self._extract_all_btn.clicked.connect(
            lambda _checked=False: self._on_extract(False))
        self._edit_btn.clicked.connect(self._on_edit)
        row.addWidget(close_btn)
        row.addWidget(self._extract_sel_btn)
        row.addWidget(self._extract_all_btn)
        row.addWidget(self._edit_btn)
        outer.addLayout(row)

        try:
            self._open_payload(data)
        except Exception as exc:
            self._error = str(exc)
        self._fill()

    # ------------------------------------------------------------- loading

    def error(self):
        return self._error

    def editable(self):
        """True when we can rebuild the archive after editing its contents."""
        return (self._container in ("cpio", "zip", "tar")
                and self._extract is not None and not self._error)

    def result_bytes(self):
        """Bytes the user packed through Edit\u2026, else None."""
        return self._packed

    def _open_payload(self, data, depth=0):
        """stdio first, then 7-Zip, then a real error with both messages."""
        kind = self.sniff(data, self._arcname)
        errors = []
        try:
            self._open_stdlib(data, depth)
            return
        except Exception as exc:
            errors.append(f"built-in decoder: {exc}")
            # a half-opened backend must not leak into the 7-Zip retry
            self._entries = []
            self._extract = None
            self._keepalive = None
            self._layers = []
            self._container = None
            self._modes = {}
        if kind != "7z":
            try:
                self._open_kind("7z", data)
                self._used_7z = True
                return
            except Exception as exc:
                errors.append(f"7-Zip: {exc}")
        raise ValueError(
            f'"{self._arcname}" could not be opened.\n\n'
            + "\n".join(errors))

    def _open_stdlib(self, data, depth=0):
        kind = self.sniff(data, self._arcname)
        if kind in ("gzip", "xz", "bz2"):
            if depth >= self._DEPTH_LIMIT:
                raise ValueError("Compression nesting is too deep.")
            self._layers.append(kind)
            if kind == "gzip":
                data = gzip.decompress(data)
            elif kind == "xz":
                data = lzma.decompress(data)
            else:
                data = bz2.decompress(data)
            self._open_stdlib(data, depth + 1)
            return
        if kind in ("cpio", "zip", "tar", "7z"):
            self._open_kind(kind, data)
            return
        raise ValueError("format not recognised by the built-in decoders")

    def _stage_temp(self, suffix):
        handle, path = tempfile.mkstemp(suffix=suffix)
        os.close(handle)
        self._temp_files.append(path)
        return path

    def _open_kind(self, kind, data):
        if kind == "cpio":
            path = self._stage_temp(".cpio")
            with open(path, "wb") as handle:
                handle.write(data)
            rows = CpioUtils.list_entries(path)
            self._entries = [
                (name.strip("/"), size, (mode & 0o170000) == 0o040000)
                for name, mode, size in rows
                if name.strip("/") and name.strip("/") != "TRAILER!!!"
            ]
            self._extract = lambda dest, names=None, p=path: CpioUtils.extract_to(
                p, dest, names)
            self._container = "cpio"
            self._modes = {
                name.strip("/"): mode for name, mode, size in rows
                if name.strip("/") and name.strip("/") != "TRAILER!!!"
            }
            return

        if kind == "zip":
            zf = zipfile.ZipFile(io.BytesIO(data))
            self._keepalive = zf
            self._entries = [(i.filename, i.file_size, i.is_dir())
                             for i in zf.infolist() if i.filename]
            def _zip_extract(dest, names=None, _zf=zf):
                if names:
                    _zf.extractall(path=dest, members=list(names))
                else:
                    _zf.extractall(path=dest)
            self._extract = _zip_extract
            self._container = "zip"
            # external_attr >> 16 is 0 on zips written by Windows tools;
            # _file_perms() then falls back to guess_mode(). Zip stores folder
            # names with a trailing slash -- strip it so they match _walk_dir().
            self._modes = {i.filename.rstrip("/"): (i.external_attr >> 16)
                           for i in zf.infolist() if i.filename}
            return

        if kind == "tar":
            tf = tarfile.open(fileobj=io.BytesIO(data))
            self._keepalive = tf
            self._entries = [(m.name, m.size, m.isdir())
                             for m in tf.getmembers() if m.name]
            def _tar_extract(dest, names=None, _tf=tf):
                if names:
                    _tf.extractall(dest, members=names, filter="data")
                else:
                    _tf.extractall(dest, filter="data")
            self._extract = _tar_extract
            self._container = "tar"
            # TarInfo.mode is only the permission bits; carry the type too
            self._modes = {
                m.name: (m.mode | (0o120000 if m.issym() else
                                   0o040000 if m.isdir() else 0o100000))
                for m in tf.getmembers() if m.name
            }
            return

        if kind == "7z":
            if not os.path.exists(SEVEN_ZIP):
                raise ValueError("7z.exe is not available.")
            path = self._stage_temp(".7z")
            with open(path, "wb") as handle:
                handle.write(data)
            result = subprocess.run(
                [SEVEN_ZIP, "l", "-slt", path],
                capture_output=True, encoding="utf-8", errors="replace",
                creationflags=CREATE_NO_WINDOW, timeout=300)
            if result.returncode != 0:
                raise ValueError(
                    "7z could not list this archive:\n"
                    + (result.stderr or result.stdout or "").strip()[:400])
            entries, current = [], None
            for line in (result.stdout or "").splitlines():
                if line.startswith("Path = "):
                    if current:
                        entries.append(current)
                    current = {"name": line[7:].strip(), "size": 0,
                               "dir": False, "header": False, "folder": False}
                elif current is not None and line.startswith("Size = "):
                    try:
                        current["size"] = int(line[7:].strip())
                    except ValueError:
                        pass
                elif current is not None and line.startswith("Folder = "):
                    current["dir"] = line[9:].strip().startswith("+")
                    current["folder"] = True
                elif current is not None and line.startswith("Type = "):
                    # present on the archive's own block, never on an entry
                    current["header"] = True
            if current:
                entries.append(current)
            # 7z prints the archive itself as the first block; drop it
            self_name = os.path.basename(path).lower()
            entries = [
                e for e in entries
                if not (e["header"] and not e["folder"])
                and e["name"].strip("/").lower() != self_name
            ]
            if not entries:
                raise ValueError("7z listed no entries for this archive.")
            self._entries = [(e["name"], e["size"], e["dir"]) for e in entries]
            def _run(dest, p=path, names=None):
                argv = [SEVEN_ZIP, "x", f"-o{dest}", "-y", p]
                if names:
                    argv.extend(names)
                proc = subprocess.run(
                    argv,
                    capture_output=True, encoding="utf-8", errors="replace",
                    creationflags=CREATE_NO_WINDOW, timeout=600)
                if proc.returncode != 0:
                    raise RuntimeError(
                        (proc.stderr or proc.stdout or "7z extraction failed").strip()[:400])
            self._extract = _run
            self._container = "7z"
            return

    def _fill(self):
        if self._error:
            self._header.setText(self._error)
            self._extract_sel_btn.setEnabled(False)
            self._extract_all_btn.setEnabled(False)
            self._edit_btn.setEnabled(False)
            return
        via = "  \u00b7  via 7-Zip" if self._used_7z else ""
        chain = "".join(f" \u2192 {x}" for x in self._layers)
        self._header.setText(
            f"{self._arcname}{chain}  \u00b7  {len(self._entries)} entries{via}")
        for name, size, is_dir in self._entries:
            item = QTreeWidgetItem([
                name,
                "" if is_dir else ImgManagerWindow._fmt_size(size),
                "Folder" if is_dir else "File",
            ])
            self._tree.addTopLevelItem(item)
        can_edit = self.editable()
        self._extract_sel_btn.setEnabled(bool(self._entries))
        self._extract_all_btn.setEnabled(bool(self._entries))
        self._edit_btn.setEnabled(can_edit)
        if can_edit:
            self._hint.setText(
                "Edits go to the staged image \u00b7 press Apply to write it")
        else:
            self._hint.setText(
                "Read-only preview \u00b7 select entries to extract only those "
                "(Ctrl+A selects all)")

    def _rebuild_from_dir(self, src_dir):
        """container bytes for an edited tree, then re-wrap in every layer
        that was peeled off when the archive was opened."""
        if self._container == "cpio":
            blob = build_cpio_from_dir(src_dir, self._modes)
        elif self._container == "zip":
            blob = build_zip_from_dir(src_dir, self._modes)
        elif self._container == "tar":
            blob = build_tar_from_dir(src_dir, self._modes)
        else:
            raise ValueError(
                f"\"{self._arcname}\" is a {self._container or 'unknown'} "
                "archive; only cpio, zip and tar can be rebuilt here.")
        for layer in reversed(self._layers):
            if layer == "gzip":
                blob = gzip.compress(blob, 9)
            elif layer == "xz":
                blob = lzma.compress(blob)
            elif layer == "bz2":
                blob = bz2.compress(blob)
            else:
                raise ValueError(f'cannot re-apply the "{layer}" layer.')
        return blob

    def _on_edit(self):
        if not self.editable() or not self._extract:
            return
        work = tempfile.mkdtemp(prefix="arcedit_")
        try:
            self._extract(work)
        except Exception as exc:
            shutil.rmtree(work, ignore_errors=True)
            QMessageBox.warning(self, "IMG Manager",
                                f"Extract failed:\n{exc}")
            return
        dlg = NestedImgDialog(
            self._arcname, None, work, self,
            extracted_dir=work, packer=self._rebuild_from_dir,
            tool_hint="rebuilt by IMG Manager")
        dlg.exec()
        packed = dlg.packed_bytes()
        shutil.rmtree(work, ignore_errors=True)
        if not packed:
            return
        self._packed = packed
        self.accept()

    def _selected_names(self):
        """Top-level entry names currently ticked in the tree (order kept)."""
        out = []
        for item in self._tree.selectedItems():
            name = item.text(0)
            if name and name not in out:
                out.append(name)
        return out

    def _expand_names(self, names):
        """Selecting a folder pulls in every entry stored beneath it."""
        expanded = []
        for name in names:
            if name not in expanded:
                expanded.append(name)
            # 7-Zip reports paths with backslashes, stdlib archives with
            # slashes -- a folder row must swallow children either way.
            base = name.rstrip("/\\")
            prefixes = (base + "/", base + "\\")
            for entry, _size, _is_dir in self._entries:
                if entry not in expanded and any(
                        entry.startswith(prefix) for prefix in prefixes):
                    expanded.append(entry)
        return expanded

    def _on_extract(self, selected_only=False):
        if not self._extract:
            return
        names = None
        if selected_only:
            picked = self._selected_names()
            if not picked:
                QMessageBox.information(
                    self, "IMG Manager",
                    "Nothing selected.\n\nCtrl+Click or Shift+Click entries "
                    "first (Ctrl+A selects everything).")
                return
            names = self._expand_names(picked)
        dest = QFileDialog.getExistingDirectory(self, "Extract to folder")
        if not dest:
            return
        try:
            result = self._extract(dest, names=names) if names is not None \
                else self._extract(dest)
        except Exception as exc:
            QMessageBox.warning(self, "IMG Manager", f"Extract failed:\n{exc}")
            return
        if isinstance(result, int) and result:
            how = f"Extracted {result} entries"
        else:
            how = f"Extracted {len(names) if names else len(self._entries)} entries"
        QMessageBox.information(self, "IMG Manager", f"{how} to:\n{dest}")

    def _on_tree_menu(self, pos):
        """Right-click: extract just the selection, everything, or select all."""
        item = self._tree.itemAt(pos)
        if item is not None and not item.isSelected():
            self._tree.clearSelection()
            self._tree.setCurrentItem(item)
            item.setSelected(True)
        has_entries = bool(self._entries) and not self._error
        has_sel = bool(self._selected_names())
        menu = QMenu(self)
        act_sel = menu.addAction("Extract selected\u2026")
        act_all = menu.addAction("Extract all\u2026")
        act_sel.setEnabled(has_entries and has_sel)
        act_all.setEnabled(has_entries)
        menu.addSeparator()
        act_a = menu.addAction("Select all\tCtrl+A")
        act_i = menu.addAction("Invert selection")
        act_c = menu.addAction("Clear selection")
        act_a.setEnabled(has_entries)
        act_i.setEnabled(has_entries)
        act_c.setEnabled(has_sel)
        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen is act_sel:
            self._on_extract(True)
        elif chosen is act_all:
            self._on_extract(False)
        elif chosen is act_a:
            self._tree.selectAll()
        elif chosen is act_i:
            self._tree.invertSelection()
        elif chosen is act_c:
            self._tree.clearSelection()

    def closeEvent(self, event):
        super().closeEvent(event)
        for path in self._temp_files:
            try:
                os.remove(path)
            except OSError:
                pass
        self._temp_files = []


class NestedImgDialog(QDialog):
    """Extract -> modify -> pack for an internal system image (.img).

    Unpacks with assets/img-checker.exe and repacks with assets/img-creater.exe,
    the exact pair InitrdManager.extract_lsp_image()/repack_lsp_image() already
    use. Everything happens in a temp folder; the caller commits the packed
    bytes into the STAGED initrd, so the live image changes only on Apply.
    """

    _STYLE = """
        QDialog { background: #171a21; color: #e6e9ef; }
        QLabel { background: transparent; color: #8a93a6; font-size: 11px; }
        QTreeWidget {
            background: #12151c; alternate-background-color: #171b24;
            color: #e6e9ef; border: 1px solid #2b3242;
            border-radius: 6px; outline: 0; font-size: 12px;
        }
        QTreeWidget::item { padding: 2px 4px; }
        QTreeWidget::item:hover { background: #1e2432; }
        QTreeWidget::item:selected { background: #2f5f9e; color: #ffffff; }
        QHeaderView::section {
            background: #1c2130; color: #aab2c5;
            border: none; border-right: 1px solid #2b3242;
            border-bottom: 1px solid #2b3242;
            padding: 4px 6px; font-size: 11px;
        }
        QPushButton {
            background: #232838; color: #e6e9ef;
            border: 1px solid #3a4150; border-radius: 5px;
            padding: 5px 14px; font-size: 12px;
        }
        QPushButton:hover { background: #2c3346; border-color: #5a6478; }
        QPushButton:pressed { background: #1b2030; }
        QPushButton:disabled { background: #1a1e27; color: #5b6272; border-color: #262b36; }
    """

    def __init__(self, arcname, data, work_root, parent=None,
                 extracted_dir=None, packer=None, tool_hint=""):
        """`extracted_dir` + `packer` reuse an already-unpacked tree instead
        of running img-checker.exe (used by the archive viewer's Edit…)."""
        super().__init__(parent)
        self.setWindowTitle(f"System image \u2014 {arcname}")
        self.setStyleSheet(self._STYLE)
        self.resize(880, 600)
        self.setMinimumSize(560, 400)

        self._arcname = arcname
        self._error = None
        self._packed = None
        self._work = None
        self._src = None
        self._img = None
        self._ops = []
        self._packer = packer
        self._tool_hint = tool_hint or "unpacked by img-checker.exe"

        try:
            if extracted_dir:
                if not os.path.isdir(extracted_dir):
                    raise ValueError(f"not a folder: {extracted_dir}")
                if packer is None:
                    raise ValueError("no packer was supplied for this folder.")
                # the caller owns this folder and cleans it up
                self._src = extracted_dir
            else:
                self._prepare(work_root, data)
                self._packer = self._pack_with_img_creater
        except Exception as exc:
            self._error = str(exc)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        self._header = QLabel("")
        outer.addWidget(self._header)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Name", "Size", "Type"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setExpandsOnDoubleClick(True)
        hdr = self._tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        outer.addWidget(self._tree, 1)

        outer.addWidget(QLabel(
            "Editing changes the extracted copy only \u2014 the image is rebuilt "
            "when you press Pack, then written to the staged initrd."))

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        for label, slot in (
                ("Open", self._on_open),
                ("Extract selected\u2026",
                 lambda: self._on_extract(True)),
                ("Extract all\u2026",
                 lambda: self._on_extract(False)),
                ("Add File\u2026", self._on_add_file),
                ("Add Folder\u2026", self._on_add_folder),
                ("New Folder", self._on_new_folder),
                ("Delete", self._on_delete),
                ("Refresh", self._on_refresh)):
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(self._STYLE)
            btn.clicked.connect(slot)
            row1.addWidget(btn)
            self._ops.append(btn)
        outer.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        row2.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(28)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFocusPolicy(Qt.NoFocus)
        cancel.setStyleSheet(self._STYLE)
        cancel.clicked.connect(self.reject)
        row2.addWidget(cancel)

        self._btn_pack = QPushButton("Pack && Save")
        self._btn_pack.setFixedHeight(28)
        self._btn_pack.setCursor(Qt.PointingHandCursor)
        self._btn_pack.setFocusPolicy(Qt.NoFocus)
        self._btn_pack.setStyleSheet("""
            QPushButton {
                background: #1558b0; color: #ffffff;
                border: 1px solid #2f7ad6; border-radius: 5px;
                padding: 5px 18px; font-weight: bold;
            }
            QPushButton:hover { background: #1a67ca; }
            QPushButton:pressed { background: #104a92; }
            QPushButton:disabled { background: #1a1e27; color: #5b6272; border-color: #262b36; }
        """)
        self._btn_pack.clicked.connect(self._on_pack)
        row2.addWidget(self._btn_pack)
        outer.addLayout(row2)

        if self._error:
            self._header.setText(self._error)
            for btn in self._ops:
                btn.setEnabled(False)
            self._btn_pack.setEnabled(False)
        else:
            self._rebuild()

    def error(self):
        return self._error

    def packed_bytes(self):
        return self._packed

    # ----------------------------------------------------------- extraction

    def _prepare(self, work_root, data):
        if not os.path.exists(IMG_EXTRACTOR):
            raise ValueError(
                "img-checker.exe is missing from assets/ \u2014 this image "
                "cannot be unpacked.")
        os.makedirs(work_root, exist_ok=True)
        self._work = tempfile.mkdtemp(prefix="sysimg_", dir=work_root)
        base = os.path.basename(self._arcname) or "image.img"
        if not base.lower().endswith(".img"):
            base += ".img"
        self._img = os.path.join(self._work, base)
        with open(self._img, "wb") as handle:
            handle.write(data)
        self._src = os.path.join(self._work, "src")
        os.makedirs(self._src, exist_ok=True)
        result = subprocess.run(
            [IMG_EXTRACTOR, f"--extract={self._src}", "--force", self._img],
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=300, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            raise ValueError(
                "img-checker.exe could not unpack this image:\n"
                + ((result.stderr or "") + (result.stdout or "")).strip()[:500])

    # ----------------------------------------------------------------- tree

    def _rebuild(self):
        self._tree.setUpdatesEnabled(False)
        self._tree.setSortingEnabled(False)
        self._tree.clear()
        count = self._add_dir("", self._tree.invisibleRootItem())
        self._tree.setSortingEnabled(True)
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setExpanded(True)
        self._tree.setUpdatesEnabled(True)
        self._header.setText(
            f"{self._arcname}  \u00b7  {count} entries  \u00b7  "
            f"{self._tool_hint}")

    def _add_dir(self, rel, parent_item):
        full = os.path.join(self._src, rel) if rel else self._src
        try:
            names = sorted(os.listdir(full), key=str.lower)
        except OSError:
            return 0
        rows = []
        for name in names:
            path = os.path.join(full, name)
            child_rel = f"{rel}/{name}" if rel else name
            rows.append((not os.path.isdir(path), name, child_rel, path))
        rows.sort(key=lambda row: (row[0], row[1].lower()))
        count = 0
        for is_file, name, child_rel, path in rows:
            if is_file:
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
            else:
                size = 0
            item = QTreeWidgetItem([
                name,
                "" if not is_file else ImgManagerWindow._fmt_size(size),
                "File" if is_file else "Folder",
            ])
            item.setData(0, Qt.UserRole, {
                "path": path, "rel": child_rel, "dir": not is_file})
            parent_item.addChild(item)
            count += 1
            if not is_file:
                count += self._add_dir(child_rel, item)
        return count

    def _selected_paths(self):
        out = []
        for item in self._tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if data:
                out.append(data)
        return out

    def _dest_dir(self):
        picked = self._selected_paths()
        if not picked:
            return self._src
        first = picked[0]
        return first["path"] if first["dir"] else os.path.dirname(first["path"])

    # ------------------------------------------------------------------ extract

    @staticmethod
    def _count_files(root):
        total = 0
        for _dirpath, _dirnames, filenames in os.walk(root):
            total += len(filenames)
        return total

    def _on_extract(self, selected_only=False):
        """Copy the tree (or just the ticked entries) out to a real folder."""
        if self._error:
            return
        if selected_only:
            picked = self._selected_paths()
            if not picked:
                self._info("Nothing selected.\n\nCtrl+Click or Shift+Click "
                           "entries first (Ctrl+A selects everything).")
                return
        else:
            picked = None
        dest = QFileDialog.getExistingDirectory(self, "Extract to folder")
        if not dest:
            return
        count = 0
        try:
            if picked is None:
                os.makedirs(dest, exist_ok=True)
                count = self._count_files(self._src)
                shutil.copytree(self._src, dest, dirs_exist_ok=True)
            else:
                for entry in picked:
                    target = (os.path.join(dest, *entry["rel"].split("/"))
                              if entry["rel"] else dest)
                    if entry["dir"]:
                        if os.path.isdir(entry["path"]):
                            count += self._count_files(entry["path"])
                            shutil.copytree(entry["path"], target,
                                            dirs_exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
                        shutil.copy2(entry["path"], target)
                        count += 1
        except Exception as exc:
            self._err(f"Extract failed:\n{exc}")
            return
        self._info(f"Extracted {count} entries to:\n{dest}")

    # -------------------------------------------------------------- actions

    @staticmethod
    def _valid_name(name):
        if not name or name in (".", ".."):
            return False
        return not any(ch in name for ch in ("/", "\\", "\x00"))

    def _err(self, text):
        QMessageBox.warning(self, "IMG Manager", text)

    def _info(self, text):
        QMessageBox.information(self, "IMG Manager", text)

    def _confirm(self, text):
        return QMessageBox.question(
            self, "IMG Manager", text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _on_open(self):
        picked = self._selected_paths()
        if len(picked) != 1:
            self._info("Select exactly one file to open.")
            return
        entry = picked[0]
        if entry["dir"]:
            self._info("Folders cannot be opened \u2014 select a file.")
            return
        try:
            with open(entry["path"], "rb") as handle:
                data = handle.read()
        except OSError as exc:
            self._err(f"Cannot read {entry['rel']}:\n{exc}")
            return
        if _looks_like_text(data):
            dlg = ScriptEditorDialog(entry["rel"], data, self)
            if dlg.exec() != QDialog.Accepted:
                return
            payload = dlg.result_bytes()
            if payload == data:
                return
            try:
                with open(entry["path"], "wb") as handle:
                    handle.write(payload)
            except OSError as exc:
                self._err(f"Save failed:\n{exc}")
                return
            self._rebuild()
            self._info(f"Saved:\n{entry['rel']}")
            return
        kind = ArchiveViewerDialog.sniff(data, entry["rel"])
        if kind is not None:
            viewer = ArchiveViewerDialog(entry["rel"], data, self)
            if viewer.error():
                self._err(viewer.error())
                return
            viewer.exec()
            return
        dest, _filter = QFileDialog.getSaveFileName(
            self, f"Save a copy of {entry['rel']}",
            entry["rel"].rpartition("/")[2])
        if not dest:
            return
        try:
            with open(dest, "wb") as handle:
                handle.write(data)
        except OSError as exc:
            self._err(f"Save failed:\n{exc}")
            return
        self._info(f"Saved a copy to:\n{dest}")

    def _on_add_file(self):
        src, _filter = QFileDialog.getOpenFileName(self, "Add file to image")
        if not src:
            return
        dest_dir = self._dest_dir()
        dest = os.path.join(dest_dir, os.path.basename(src))
        if os.path.exists(dest) and not self._confirm(
                f"{os.path.basename(src)} already exists here.\nReplace it?"):
            return
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            self._err(f"Add file failed:\n{exc}")
            return
        self._rebuild()

    def _on_add_folder(self):
        src = QFileDialog.getExistingDirectory(self, "Add folder to image")
        if not src:
            return
        base = os.path.basename(os.path.normpath(src))
        if not base:
            self._err("Cannot determine the folder name.")
            return
        dest = os.path.join(self._dest_dir(), base)
        if os.path.exists(dest):
            if not self._confirm(f"/{base} already exists here.\nReplace it?"):
                return
            try:
                shutil.rmtree(dest)
            except OSError as exc:
                self._err(f"Replace failed:\n{exc}")
                return
        try:
            shutil.copytree(src, dest)
        except OSError as exc:
            self._err(f"Add folder failed:\n{exc}")
            return
        self._rebuild()

    def _on_new_folder(self):
        text, ok = QInputDialog.getText(self, "IMG Manager", "New folder name:")
        if not ok:
            return
        name = text.strip().strip("/")
        if not self._valid_name(name):
            if name:
                self._err("Invalid name: no slashes, backslashes or dots.")
            return
        dest = os.path.join(self._dest_dir(), name)
        if os.path.exists(dest):
            self._err(f"/{name} already exists here.")
            return
        try:
            os.makedirs(dest)
        except OSError as exc:
            self._err(f"Create failed:\n{exc}")
            return
        self._rebuild()

    def _on_delete(self):
        picked = self._selected_paths()
        if not picked:
            self._info("Select one or more entries to delete.")
            return
        word = "entry" if len(picked) == 1 else "entries"
        if not self._confirm(f"Delete {len(picked)} selected {word} from "
                             "the extracted copy?"):
            return
        for entry in picked:
            try:
                if entry["dir"]:
                    shutil.rmtree(entry["path"])
                else:
                    os.remove(entry["path"])
            except OSError as exc:
                self._err(f"Delete failed:\n{exc}")
                break
        self._rebuild()

    def _on_refresh(self):
        self._rebuild()

    def _on_pack(self):
        """Rebuild the archive/image and hand the bytes to the caller."""
        if self._packer is None:
            self._err("There is nothing to pack.")
            return
        try:
            packed = self._packer(self._src)
        except Exception as exc:
            self._err(f"Pack failed:\n{exc}")
            return
        if not packed:
            self._err("Packing produced no data.")
            return
        self._packed = packed
        self.accept()

    def _pack_with_img_creater(self, src_dir):
        """Rebuild an .img with the bundled img-creater.exe (returns bytes)."""
        if not os.path.exists(IMG_CREATER):
            raise ValueError("img-creater.exe is missing from assets/.")
        out = os.path.join(self._work, "packed.img")
        if os.path.exists(out):
            try:
                os.remove(out)
            except OSError:
                pass
        try:
            result = subprocess.run(
                [IMG_CREATER, "-zlz4hc,9", out, src_dir],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=600, creationflags=CREATE_NO_WINDOW)
        except Exception as exc:
            raise ValueError(f"img-creater.exe failed:\n{exc}")
        if result.returncode != 0 or not os.path.isfile(out):
            detail = ((result.stderr or "") + (result.stdout or "")).strip()[:500]
            raise ValueError("img-creater.exe could not pack this image:\n"
                             + detail)
        try:
            with open(out, "rb") as handle:
                return handle.read()
        except OSError as exc:
            raise ValueError(f"Cannot read the packed image:\n{exc}")

    def done(self, result):
        super().done(result)
        if self._work:
            shutil.rmtree(self._work, ignore_errors=True)
            self._work = None


class LogSignals(QObject):
    log_updated = Signal(str)
    close_requested = Signal()


class _LineTee:
    """sys.stdout stand-in used while a printing CLI function runs.

    Buffers partial writes and forwards every completed line to `sink`, so the
    transcript reaches the log window and, through it, the real terminal.
    """

    def __init__(self, sink):
        self._sink = sink
        self._buf = ""

    def write(self, text):
        self._buf += str(text)
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._sink(line.rstrip())
        return len(text)

    def flush(self):
        if self._buf.strip():
            self._sink(self._buf.rstrip())
        self._buf = ""

    def isatty(self):
        return False

    def fileno(self):
        try:
            return sys.__stdout__.fileno()
        except Exception:
            raise io.UnsupportedOperation("fileno")

    @property
    def encoding(self):
        return "utf-8"


class LogDialog(QDialog):
    """Scrolling transcript of one CLI operation.

    Same contract as RecoveryWindow -- update_log(msg) / request_close() -- so
    every existing _flow_* runs here unchanged, but the whole log stays on
    screen (Copy / Save log) while the caller's log() echoes it to the terminal.
    """

    _STYLE = """
        QDialog { background: #171a21; color: #e6e9ef; }
        QLabel { background: transparent; color: #e6e9ef;
                 font-size: 13px; font-weight: bold; }
        QPlainTextEdit {
            background: #12151c; color: #d7dce6; border: 1px solid #2b3242;
            border-radius: 6px; outline: 0; selection-background-color: #2f5f9e;
        }
        QPushButton {
            background: #232838; color: #e6e9ef;
            border: 1px solid #3a4150; border-radius: 5px;
            padding: 5px 14px; font-size: 12px;
        }
        QPushButton:hover { background: #2c3346; border-color: #5a6478; }
        QPushButton:pressed { background: #1b2030; }
        QPushButton:disabled { background: #1a1e27; color: #5b6272;
                               border-color: #262b36; }
    """

    def __init__(self, title="Working", parent=None):
        super().__init__(parent)
        self._title = title
        self.setWindowTitle(title)
        self.setStyleSheet(self._STYLE)
        self.resize(780, 470)
        self.setMinimumSize(520, 320)
        self._finished = False
        # the real terminal, captured before anything redirects stdout
        self._real_out = sys.__stdout__
        self._signals = LogSignals()
        self._signals.log_updated.connect(self._append)
        self._signals.close_requested.connect(self._finish)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        self._head = QLabel(title)
        outer.addWidget(self._head)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(20000)
        self._text.setLineWrapMode(QPlainTextEdit.NoWrap)
        mono = QFont("Consolas", 10)
        mono.setStyleHint(QFont.Monospace)
        self._text.setFont(mono)
        outer.addWidget(self._text, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        for label, slot in (("Copy all", self._copy_all),
                            ("Save log\u2026", self._save_log)):
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #1558b0; color: #ffffff;
                border: 1px solid #2f7ad6; border-radius: 5px;
                padding: 5px 18px; font-weight: bold;
            }
            QPushButton:hover { background: #1a67ca; }
        """)
        close_btn.clicked.connect(self.reject)
        row.addWidget(close_btn)
        outer.addLayout(row)

    # ------------------------------------------------------- worker-facing API

    def log(self, msg):
        """The `log` callable handed to every _flow_* (also hits the terminal)."""
        text = str(msg)
        try:
            print(f"  {text}", file=self._real_out, flush=True)
        except Exception:
            pass
        self.update_log(text)

    def update_log(self, msg):
        try:
            self._signals.log_updated.emit(str(msg))
        except RuntimeError:
            pass  # the dialog is already gone

    def request_close(self):
        try:
            self._signals.close_requested.emit()
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ slots

    def _append(self, msg):
        stamp = time.strftime("%H:%M:%S")
        self._text.appendPlainText(f"[{stamp}] {msg}" if msg else "")
        bar = self._text.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _finish(self):
        if self._finished:
            return
        self._finished = True
        self._text.appendPlainText("")
        self._text.appendPlainText(
            f"[{time.strftime('%H:%M:%S')}] finished \u2014 you can copy or "
            "save this log, then close the window")
        self._head.setText(f"{self._title}  \u2014  finished")
        self.setWindowTitle(f"{self._title} \u2014 finished")

    def finished_run(self):
        return self._finished

    # ---------------------------------------------------------------- actions

    def _copy_all(self):
        QApplication.clipboard().setText(self._text.toPlainText())
        self._head.setText(f"{self._title}  \u2014  copied to clipboard")

    def _save_log(self):
        path, _filter = QFileDialog.getSaveFileName(
            self, "Save log", "twrp-log.txt",
            "Text files (*.txt);;All files (*.*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(self._text.toPlainText())
        except OSError as exc:
            QMessageBox.warning(self, "IMG Manager", f"Save failed:\n{exc}")
            return
        self._head.setText(f"{self._title}  \u2014  saved: {path}")

    # ---------------------------------------------------------------- runners

    def run_flow(self, flow_func, flow_args=None):
        """Start a (log, window, **args) flow on a worker thread."""
        kwargs = dict(flow_args or {})

        def worker():
            try:
                flow_func(self.log, self, **kwargs)
            except Exception as exc:
                try:
                    print(f"  ERROR: {exc}", flush=True)
                except Exception:
                    pass
                self.update_log(f"Error: {exc}")
            finally:
                self.request_close()

        threading.Thread(target=worker, daemon=True).start()
        return self

    def run_printing(self, func, args=None):
        """Run a CLI function that only prints(); replay its output line by
        line into this dialog and the terminal."""
        kwargs = dict(args or {})

        def worker():
            previous = sys.stdout
            sys.stdout = _LineTee(self.log)
            try:
                func(**kwargs)
            except Exception as exc:
                self.log(f"Error: {exc}")
            finally:
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
                sys.stdout = previous
                self.request_close()

        threading.Thread(target=worker, daemon=True).start()
        return self


class InfoDialog(LogDialog):
    """The same transcript shell, filled in one go instead of streamed."""

    def __init__(self, title, text, parent=None):
        super().__init__(title, parent)
        self._text.setPlainText(text)
        self._head.setText(title)

    def _finish(self):
        self._finished = True


class ImgManagerWindow(QWidget):
    """7-Zip style manager for the initrd.img cpio archive.

    Custom-painted frameless shell (same idiom as PermissionManagerWindow)
    with standard Qt widgets inside: a toolbar, a multi-column multi-select
    tree, a status line and a persistent no-backup warning.
    """

    W = 1100
    H = 700
    HDR_H = 46
    RADIUS = 14
    CTL_SIZE = 26
    MAX_HISTORY = 40

    _ACTIONS = (
        ("open", "Open"),
        ("extract", "Extract"),
        ("delete", "Delete"),
        ("rename", "Rename"),
        ("overwrite", "Overwrite"),
        ("add_file", "Add File"),
        ("add_folder", "Add Folder"),
        ("new_folder", "New Folder"),
        ("refresh", "Refresh"),
    )

    # Every CLI argument that makes sense while an image is open, in the order
    # the two extra toolbar rows show them. Each key maps to self._cli_<key>().
    _CLI_ACTIONS = (
        ("info", "Info"),
        ("install_app", "Install as system app\u2026"),
        ("update_app", "Update as system app\u2026"),
        ("enable", "Enable TWRP"),
        ("disable", "Disable TWRP"),
        ("install_twrp", "Install TWRP"),
        ("repair_twrp", "Repair TWRP"),
        ("uninstall_twrp", "Uninstall TWRP"),
        ("install_hook", "Install hook"),
        ("repair_hook", "Repair hook"),
        ("uninstall_hook", "Uninstall hook"),
        ("cleanup_uninstall", "Uninstall temp cleanup"),
        ("status", "Status"),
        ("list_apps", "List system apps"),
        ("uninstall_app", "Uninstall system app\u2026"),
        ("register_img", "Register .img"),
        ("unregister_img", "Unregister .img"),
    )

    # Extra hover text for individual _CLI_ACTIONS buttons (key -> tooltip).
    _BTN_TOOLTIPS = {
        "cleanup_uninstall":
            "Delete overlay.d/sbin/uninstall.txt (the pending uninstall list)\n"
            "from the image. Run it ONCE after the boot that applied an\n"
            "uninstall - otherwise the same list runs on every boot and\n"
            "would remove the app again if you reinstall it later.",
    }

    _BTN_STYLE = """
        QPushButton {
            background: #232838; color: #e6e9ef;
            border: 1px solid #3a4150; border-radius: 5px;
            padding: 4px 10px;
        }
        QPushButton:hover { background: #2c3346; border-color: #5a6478; }
        QPushButton:pressed { background: #1b2030; }
        QPushButton:disabled { background: #1a1e27; color: #5b6272; border-color: #262b36; }
    """

    # the one button that writes the live image
    _BTN_APPLY = """
        QPushButton {
            background: #1558b0; color: #ffffff;
            border: 1px solid #2f7ad6; border-radius: 5px;
            padding: 4px 18px; font-weight: bold;
        }
        QPushButton:hover { background: #1a67ca; }
        QPushButton:pressed { background: #104a92; }
        QPushButton:disabled { background: #1a1e27; color: #5b6272; border-color: #262b36; }
    """

    # red = no backup on disk yet, green = at least one backup exists
    _BTN_BACKUP_NONE = """
        QPushButton {
            background: #7a1f1f; color: #ffd9d9;
            border: 1px solid #b3392f; border-radius: 5px;
            padding: 4px 14px; font-weight: bold;
        }
        QPushButton:hover { background: #93271f; border-color: #d0453a; }
        QPushButton:pressed { background: #5c1616; }
    """

    _BTN_BACKUP_OK = """
        QPushButton {
            background: #1c5c2e; color: #d9ffe3;
            border: 1px solid #2f9e4a; border-radius: 5px;
            padding: 4px 14px; font-weight: bold;
        }
        QPushButton:hover { background: #247a3c; border-color: #3ec164; }
        QPushButton:pressed { background: #14461f; }
    """

    _TREE_STYLE = """
        QTreeWidget {
            background: #12151c; alternate-background-color: #171b24;
            color: #e6e9ef; border: 1px solid #2b3242;
            border-radius: 8px; outline: 0; font-size: 12px;
        }
        QTreeWidget::item { padding: 3px 4px; }
        QTreeWidget::item:hover { background: #1e2432; }
        QTreeWidget::item:selected { background: #2f5f9e; color: #ffffff; }
        QTreeWidget::item:selected:!active { background: #2f5f9e; color: #ffffff; }
        QHeaderView::section {
            background: #1c2130; color: #aab2c5;
            border: none; border-right: 1px solid #2b3242;
            border-bottom: 1px solid #2b3242;
            padding: 4px 6px; font-size: 11px;
        }
    """

    def __init__(self, initrd_path, source_path=None):
        super().__init__()
        # Every edit lands in a temp copy of the image; the live file is only
        # written by the Apply button, so a mistake can never break the boot.
        self._real_path = initrd_path
        self._stage_dir = tempfile.mkdtemp(prefix="imgmgr_")
        self._path = os.path.join(
            self._stage_dir, os.path.basename(initrd_path) or "initrd.img")
        shutil.copy2(source_path or initrd_path, self._path)
        self._mgr = InitrdManager(self._path)
        # the CLI/flow engine the extra toolbar buttons drive
        self._twrp = WSATWRP()
        self._hist_dir = os.path.join(self._stage_dir, "history")
        os.makedirs(self._hist_dir, exist_ok=True)
        self._hist = []
        self._hist_seq = 0
        self._hpos = -1
        self._real_hash = self._file_hash(initrd_path)

        self._entries = {}
        self._last_action = ""
        self._dirty = False
        self._drag_offset = None
        self._hover = None
        self._close_rect = None
        self._max_rect = None
        self._min_rect = None
        self._grip = None
        self._undo_btn = None
        self._redo_btn = None
        self._restore_btn = None
        self._btn_backup = None
        self._apply_btn = None
        self._admin_cb = None
        self._base_title = f"IMG Manager  \u2014  {os.path.basename(initrd_path)}"
        self._title_text = self._base_title
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setMinimumSize(860, 480)
        self.resize(self.W, self.H)
        self._build_layout()
        self._push_snapshot()
        self._reload()
        self._refresh_buttons()

    def _build_layout(self):
        self._update_control_rects()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, self.HDR_H + 10, 14, 6)
        outer.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(6)
        for key, label in self._ACTIONS:
            if key == "open":
                continue  # reachable from the context menu only
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(self._BTN_STYLE)
            btn.clicked.connect(lambda _checked=False, k=key: self._on_action(k))
            row.addWidget(btn)
        row.addStretch(1)

        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setFixedHeight(28)
        self._undo_btn.setCursor(Qt.PointingHandCursor)
        self._undo_btn.setFocusPolicy(Qt.NoFocus)
        self._undo_btn.setStyleSheet(self._BTN_STYLE)
        self._undo_btn.clicked.connect(self._undo)
        row.addWidget(self._undo_btn)

        self._redo_btn = QPushButton("Redo")
        self._redo_btn.setFixedHeight(28)
        self._redo_btn.setCursor(Qt.PointingHandCursor)
        self._redo_btn.setFocusPolicy(Qt.NoFocus)
        self._redo_btn.setStyleSheet(self._BTN_STYLE)
        self._redo_btn.clicked.connect(self._redo)
        row.addWidget(self._redo_btn)
        outer.addLayout(row)

        # row 2 -- image info, system-app install/update (+ Admin tick) and
        # the two TWRP switches that used to be CLI-only
        cli = dict(self._CLI_ACTIONS)
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        for key in ("info", "install_app", "update_app"):
            row2.addWidget(self._cli_button(cli[key], key))

        self._admin_cb = QCheckBox("Admin")
        self._admin_cb.setStyleSheet(
            "QCheckBox { background: transparent; color: #e0a030; "
            "font-size: 12px; font-weight: bold; spacing: 5px; }"
            "QCheckBox::indicator { width: 15px; height: 15px; }")
        self._admin_cb.setToolTip(
            "Install / Update as system app into the ADMIN module.\n"
            f"Needs the password; {ADMIN_PASSWORD_ATTEMPTS} wrong tries "
            "disable the tick for this session and the operation then runs "
            "as the USER module.")
        self._admin_cb.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self._admin_cb)
        row2.addStretch(1)
        for key in ("enable", "disable"):
            row2.addWidget(self._cli_button(cli[key], key))
        outer.addLayout(row2)

        # row 3 -- TWRP lifecycle on the left, boot-hook lifecycle on the right
        row3 = QHBoxLayout()
        row3.setSpacing(6)
        for key in ("install_twrp", "repair_twrp", "uninstall_twrp"):
            row3.addWidget(self._cli_button(cli[key], key))
        row3.addStretch(1)
        for key in ("install_hook", "repair_hook", "uninstall_hook",
                    "cleanup_uninstall"):
            row3.addWidget(self._cli_button(cli[key], key))
        outer.addLayout(row3)

        # row 4 -- status, system-app listing/removal and the .img handlers
        row4 = QHBoxLayout()
        row4.setSpacing(6)
        for key in ("status", "list_apps", "uninstall_app"):
            row4.addWidget(self._cli_button(cli[key], key))
        row4.addStretch(1)
        for key in ("register_img", "unregister_img"):
            row4.addWidget(self._cli_button(cli[key], key))
        outer.addLayout(row4)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(5)
        self._tree.setHeaderLabels(["Name", "Size", "Type", "Mode", "Path"])
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.setStyleSheet(self._TREE_STYLE)
        hdr = self._tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.Interactive)
        self._tree.setColumnWidth(4, 300)
        outer.addWidget(self._tree, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        self._restore_btn = QPushButton("Restore\u2026")
        self._restore_btn.setFixedHeight(28)
        self._restore_btn.setCursor(Qt.PointingHandCursor)
        self._restore_btn.setFocusPolicy(Qt.NoFocus)
        self._restore_btn.setStyleSheet(self._BTN_STYLE)
        self._restore_btn.clicked.connect(self._act_restore)
        bottom.addWidget(self._restore_btn)

        # colour reports whether a backup exists on disk
        self._btn_backup = QPushButton("Backup")
        self._btn_backup.setFixedHeight(28)
        self._btn_backup.setCursor(Qt.PointingHandCursor)
        self._btn_backup.setFocusPolicy(Qt.NoFocus)
        self._btn_backup.clicked.connect(self._act_backup)
        bottom.addWidget(self._btn_backup)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setFixedHeight(28)
        self._apply_btn.setCursor(Qt.PointingHandCursor)
        self._apply_btn.setFocusPolicy(Qt.NoFocus)
        self._apply_btn.setStyleSheet(self._BTN_APPLY)
        self._apply_btn.clicked.connect(self._act_apply)
        bottom.addWidget(self._apply_btn)

        bottom.addStretch(1)

        self._warn = QLabel(
            "Staged edits only \u2014 nothing touches the live image until "
            "you press Apply.")
        self._warn.setFixedHeight(16)
        self._warn.setStyleSheet("color: #e0a030; font-size: 11px;")
        bottom.addWidget(self._warn)
        outer.addLayout(bottom)

        self._status = QLabel("")
        self._status.setFixedHeight(16)
        self._status.setStyleSheet("color: #8a93a6; font-size: 11px;")
        outer.addWidget(self._status)

        self._grip = QSizeGrip(self)

    # ---------------------------------------------------------------- paint

    @staticmethod
    def _font(size, weight=QFont.Normal):
        f = QFont("Segoe UI")
        f.setPixelSize(size)
        f.setWeight(weight)
        f.setStyleStrategy(QFont.PreferAntialias)
        return f

    def paintEvent(self, _event):
        radius = 0 if self.isMaximized() else self.RADIUS
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        box = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(QColor("#3a4150"), 1.5))
        painter.setBrush(QColor("#171a21"))
        painter.drawRoundedRect(box, radius, radius)

        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(box, radius, radius)
        painter.setClipPath(clip)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1f2430"))
        painter.drawRect(QRectF(0, 0, self.width(), self.HDR_H))
        painter.setPen(QPen(QColor("#2b3242"), 1))
        painter.drawLine(8, self.HDR_H, self.width() - 8, self.HDR_H)
        painter.restore()

        painter.setPen(QColor("#e6e9ef"))
        painter.setFont(self._font(15, QFont.DemiBold))
        painter.drawText(16, 0, self.width() - 140, self.HDR_H,
                         Qt.AlignVCenter | Qt.AlignLeft, self._title_text)

        for kind in ("min", "max", "close"):
            self._draw_control(painter, kind)

    def _draw_control(self, painter, kind):
        rect = {"min": self._min_rect, "max": self._max_rect,
                "close": self._close_rect}[kind]
        if not rect:
            return
        x, y, size = rect
        hovered = self._hover == kind
        if kind == "close":
            bg = QColor("#c0392b") if hovered else QColor("#2f3747")
        else:
            bg = QColor("#3c4557") if hovered else QColor("#2f3747")
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(x, y, size, size), 6, 6)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        if kind == "close":
            painter.drawLine(x + 8, y + 8, x + size - 8, y + size - 8)
            painter.drawLine(x + size - 8, y + 8, x + 8, y + size - 8)
        elif kind == "min":
            painter.drawLine(x + 8, y + size - 9, x + size - 8, y + size - 9)
        elif self.isMaximized():
            painter.drawRect(QRectF(x + 7, y + 7, size - 17, size - 17))
            painter.drawRect(QRectF(x + 11, y + 11, size - 17, size - 17))
        else:
            painter.drawRect(QRectF(x + 7, y + 7, size - 14, size - 14))

    def _update_control_rects(self):
        size = self.CTL_SIZE
        gap = 6
        margin = 12
        y = (self.HDR_H - size) // 2
        x_close = self.width() - margin - size
        x_max = x_close - gap - size
        x_min = x_max - gap - size
        self._close_rect = (x_close, y, size)
        self._max_rect = (x_max, y, size)
        self._min_rect = (x_min, y, size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_control_rects()
        if self._grip is not None:
            hint = self._grip.sizeHint()
            self._grip.move(self.width() - hint.width() - 2,
                            self.height() - hint.height() - 2)

    # ---------------------------------------------------------------- mouse

    @staticmethod
    def _hit(rect, pos):
        if not rect:
            return False
        x, y, size = rect
        return x <= pos.x() <= x + size and y <= pos.y() <= y + size

    def _control_at(self, pos):
        for kind in ("min", "max", "close"):
            if self._hit(getattr(self, f"_{kind}_rect"), pos):
                return kind
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position()
        control = self._control_at(pos)
        if control == "close":
            self.close()
            event.accept()
            return
        if control == "min":
            self.showMinimized()
            event.accept()
            return
        if control == "max":
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
            event.accept()
            return
        if pos.y() <= self.HDR_H and not self.isMaximized():
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        hovering = self._control_at(event.position())
        if hovering != self._hover:
            self._hover = hovering
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = None

    # ------------------------------------------------------------ tree build

    @staticmethod
    def _fmt_size(count):
        if count >= 1024 * 1024:
            return f"{count / (1024 * 1024):.1f} MB"
        if count >= 1024:
            return f"{count / 1024:.1f} KB"
        return f"{count} B"

    @staticmethod
    def _kind_label(mode):
        kind = mode & 0o170000
        if kind == 0o040000:
            return "Folder"
        if kind == 0o120000:
            return "Symlink"
        if kind == 0o100000:
            return "File"
        return "Other"

    @staticmethod
    def _mode_label(mode):
        return f"{mode & 0o7777:04o}"

    def _reload(self):
        try:
            raw = self._mgr.list_tree()
        except Exception as exc:
            self._entries = {}
            self._tree.clear()
            self._last_action = f"cannot read image: {exc}"
            self._update_status()
            return

        entries = []
        for name, mode, size in raw:
            bare = name.strip("/")
            if not bare or bare == "TRAILER!!!":
                continue
            entries.append((bare, mode, size))
        self._entries = {bare: (mode, size) for bare, mode, size in entries}

        children = {}
        for bare in self._entries:
            children.setdefault(bare.rpartition("/")[0], []).append(bare)

        # a folder can be implied only by its children; synthesise a node
        virtual = set()
        for bare in list(self._entries):
            parts = bare.split("/")
            for i in range(1, len(parts)):
                parent = "/".join(parts[:i])
                if parent not in self._entries:
                    self._entries[parent] = (0o040755, 0)
                    virtual.add(parent)
                    children.setdefault(parent.rpartition("/")[0], []).append(parent)

        self._tree.setUpdatesEnabled(False)
        self._tree.setSortingEnabled(False)
        self._tree.clear()
        self._add_children("", self._tree.invisibleRootItem(), children, virtual)
        self._tree.setSortingEnabled(True)
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setExpanded(True)
        self._tree.setUpdatesEnabled(True)
        self._update_status()

    def _add_children(self, parent_path, parent_item, children, virtual):
        def sort_key(name):
            mode = self._entries[name][0]
            return (0 if (mode & 0o170000) == 0o040000 else 1,
                    name.rpartition("/")[2].lower())

        for child in sorted(children.get(parent_path, []), key=sort_key):
            mode, size = self._entries[child]
            is_dir = (mode & 0o170000) == 0o040000
            item = QTreeWidgetItem([
                child.rpartition("/")[2],
                "" if is_dir else self._fmt_size(size),
                self._kind_label(mode),
                "\u2014" if child in virtual else self._mode_label(mode),
                "/" + child,
            ])
            item.setData(0, Qt.UserRole, {"name": child, "mode": mode, "dir": is_dir})
            parent_item.addChild(item)
            if is_dir:
                self._add_children(child, item, children, virtual)

    def _update_status(self):
        selected = len(self._tree.selectedItems())
        text = f"{len(self._entries)} entries \u00b7 {selected} selected"
        text += "  \u00b7  staged (not applied)" if self._dirty \
            else "  \u00b7  in sync"
        if self._last_action:
            text += f"  \u00b7  {self._last_action}"
        self._status.setText(text)
        self._title_text = ("*" if self._dirty else "") + self._base_title
        self.update()

    def _on_selection_changed(self):
        self._update_status()

    # ------------------------------------------------------------- helpers

    def _selected(self):
        out, seen = [], set()
        for item in self._tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if data and data["name"] not in seen:
                seen.add(data["name"])
                out.append(data["name"])
        return out

    def _single_selection(self):
        names = self._selected()
        if len(names) != 1:
            return None
        name = names[0]
        mode, _size = self._entries.get(name, (0, 0))
        return name, mode, (mode & 0o170000) == 0o040000

    def _dest_for_add(self):
        """Folder the next Add/New Folder operation lands in."""
        info = self._single_selection()
        if info is None:
            return ""
        name, _mode, is_dir = info
        return name if is_dir else name.rpartition("/")[0]

    def _backup_files(self):
        """Backups of the LIVE image, named <file>.img.bak-YYYYMMDD-HHMMSS."""
        folder = os.path.dirname(self._real_path) or "."
        prefix = os.path.basename(self._real_path) + ".bak-"
        try:
            return sorted(name for name in os.listdir(folder)
                          if name.startswith(prefix))
        except OSError:
            return []

    def _refresh_backup_button(self):
        """Red = no backup on disk, green = at least one exists."""
        if self._btn_backup is None:
            return
        found = self._backup_files()
        if found:
            self._btn_backup.setStyleSheet(self._BTN_BACKUP_OK)
            self._btn_backup.setToolTip(
                f"{len(found)} backup(s) exist \u2014 click to make another")
            self._restore_btn.setEnabled(True)
            self._restore_btn.setToolTip(
                f"{len(found)} backup(s) \u2014 replace the staged image")
        else:
            self._btn_backup.setStyleSheet(self._BTN_BACKUP_NONE)
            self._btn_backup.setToolTip(
                "No backup yet \u2014 click to back up the image now")
            self._restore_btn.setEnabled(False)
            self._restore_btn.setToolTip("No backup to restore from")

    # ------------------------------------------------- staging + history

    @staticmethod
    def _file_hash(path):
        try:
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return None

    def _push_snapshot(self):
        """Record the current staged image so Undo can come back to it."""
        if self._hpos < len(self._hist) - 1:
            for stale in self._hist[self._hpos + 1:]:
                try:
                    os.remove(stale)
                except OSError:
                    pass
            self._hist = self._hist[:self._hpos + 1]
        while len(self._hist) >= self.MAX_HISTORY:
            try:
                os.remove(self._hist.pop(0))
            except (OSError, IndexError):
                pass
            self._hpos -= 1
        self._hist_seq += 1
        path = os.path.join(self._hist_dir, f"{self._hist_seq:05d}.img")
        try:
            shutil.copy2(self._path, path)
        except OSError:
            return
        self._hist.append(path)
        self._hpos = len(self._hist) - 1
        self._after_history_change()

    def _after_history_change(self):
        self._update_dirty()
        self._refresh_buttons()
        self._update_status()

    def _update_dirty(self):
        self._dirty = self._file_hash(self._path) != self._real_hash

    def _load_snapshot(self, path):
        shutil.copy2(path, self._path)
        self._mgr = InitrdManager(self._path)
        self._reload()
        self._after_history_change()

    def _undo(self):
        if self._hpos <= 0:
            return
        self._hpos -= 1
        self._load_snapshot(self._hist[self._hpos])
        self._last_action = f"undo ({self._hpos + 1}/{len(self._hist)})"
        self._update_status()

    def _redo(self):
        if self._hpos >= len(self._hist) - 1:
            return
        self._hpos += 1
        self._load_snapshot(self._hist[self._hpos])
        self._last_action = f"redo ({self._hpos + 1}/{len(self._hist)})"
        self._update_status()

    def _reset_history(self):
        for path in self._hist:
            try:
                os.remove(path)
            except OSError:
                pass
        self._hist = []
        self._hpos = -1
        self._push_snapshot()

    def _commit_op(self, description, callback):
        """Run a mutating operation on the staged image, then remember it."""
        try:
            callback()
        except Exception as exc:
            self._err(f"{description} failed:\n{exc}")
            self._reload()
            return False
        self._push_snapshot()
        self._last_action = description
        self._reload()
        self._refresh_buttons()
        return True

    def _refresh_buttons(self):
        if self._undo_btn is not None:
            self._undo_btn.setEnabled(self._hpos > 0)
            self._undo_btn.setToolTip("Ctrl+Z")
        if self._redo_btn is not None:
            self._redo_btn.setEnabled(self._hpos < len(self._hist) - 1)
            self._redo_btn.setToolTip("Ctrl+Y")
        if self._apply_btn is not None:
            self._apply_btn.setEnabled(bool(self._dirty))
            self._apply_btn.setToolTip(
                "Write the staged image over the live one" if self._dirty
                else "Nothing to apply \u2014 staged image matches the live one")
        if self._btn_backup is not None:
            self._refresh_backup_button()

    @staticmethod
    def _valid_name(name):
        if not name or name in (".", ".."):
            return False
        return not any(ch in name for ch in ("/", "\\", "\x00"))

    def _info(self, text):
        QMessageBox.information(self, "IMG Manager", text)

    def _err(self, text):
        QMessageBox.warning(self, "IMG Manager", text)

    def _confirm(self, text):
        return QMessageBox.question(
            self, "IMG Manager", text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------ actions

    def _on_action(self, key):
        for action_key, _label in self._ACTIONS:
            if action_key == key:
                getattr(self, f"_act_{key}")()
                return

    # -------------------------------------------------------- CLI buttons

    def _cli_button(self, label, key):
        """Toolbar button for one _CLI_ACTIONS entry."""
        btn = QPushButton(label)
        btn.setFixedHeight(28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(self._BTN_STYLE)
        tip = self._BTN_TOOLTIPS.get(key)
        if tip:
            btn.setToolTip(tip)
        btn.clicked.connect(lambda _checked=False, k=key: self._on_cli(k))
        return btn

    def _on_cli(self, key):
        handler = getattr(self, f"_cli_{key}", None)
        if handler is not None:
            handler()

    def _confirm_live(self, what):
        """CLI operations write the LIVE image, not this window's staging."""
        if self._dirty and not self._confirm(
                f"You have unapplied staged edits.\n"
                f"Operations that {what} write the LIVE image \u2014 applying "
                "your staged edits afterwards would overwrite that work.\n\n"
                "Continue anyway?"):
            return False
        return True

    def _after_live_change(self):
        """A CLI run may have rewritten the live image behind our back."""
        new_hash = self._file_hash(self._real_path)
        if new_hash is None or new_hash == self._real_hash:
            return
        if not self._confirm(
                "The live image changed on disk.\n"
                "Reload it into this window (your staged edits are discarded)?"):
            self._last_action = "live image changed on disk (not reloaded)"
            self._update_status()
            return
        try:
            shutil.copy2(self._real_path, self._path)
        except OSError as exc:
            self._err(f"Reload failed:\n{exc}")
            return
        self._mgr = InitrdManager(self._path)
        self._real_hash = new_hash
        self._reset_history()
        self._reload()
        self._last_action = "reloaded from disk"
        self._update_status()

    def _admin_gate(self):
        """Password check for the Admin tick.

        Returns "admin" (tick + right password), "user" (tick off, or the
        password failed ADMIN_PASSWORD_ATTEMPTS times and the tick is now
        disabled) or None (the user cancelled -- run nothing)."""
        if not self._admin_cb.isChecked():
            return "user"
        env = os.environ.get("WSA_ADMIN_PASSWORD", "")
        if env and hashlib.sha256(
                env.encode("utf-8")).hexdigest() == ADMIN_PASSWORD_SHA256:
            self._last_action = "admin password accepted (WSA_ADMIN_PASSWORD)"
            self._update_status()
            return "admin"
        for attempt in range(1, ADMIN_PASSWORD_ATTEMPTS + 1):
            text, ok = QInputDialog.getText(
                self, "Admin password",
                f"Password for the admin module "
                f"(attempt {attempt} of {ADMIN_PASSWORD_ATTEMPTS}):",
                QLineEdit.EchoMode.Password)
            if not ok:
                return None
            if hashlib.sha256(
                    (text or "").encode("utf-8")).hexdigest() == ADMIN_PASSWORD_SHA256:
                return "admin"
            QMessageBox.warning(
                self, "Admin password",
                f"Wrong password ({attempt}/{ADMIN_PASSWORD_ATTEMPTS}).")
        # three misses: drop the tick and carry on as the user module
        self._admin_cb.setChecked(False)
        self._admin_cb.setEnabled(False)
        self._admin_cb.setToolTip(
            f"Disabled after {ADMIN_PASSWORD_ATTEMPTS} wrong passwords \u2014 "
            "this session runs as the user module.")
        QMessageBox.information(
            self, "Admin password",
            f"{ADMIN_PASSWORD_ATTEMPTS} wrong passwords.\n\nThe Admin tick is "
            "now disabled for this session and the operation runs as the "
            "USER module.")
        return "user"

    @staticmethod
    def _default_profile():
        """Same fallback the CLI uses when no permission window is answered."""
        return {
            "hide_uninstall": True,
            "hide_disable": True,
            "privapp_perms": sorted(PRIVILEGED_PERMS),
            "runtime_perms": list(DANGEROUS_PERMS) + list(SPECIAL_PERMS),
            "fixed_runtime_perms": list(DANGEROUS_PERMS) + list(SPECIAL_PERMS),
        }

    def _collect_profiles(self, apk_paths):
        """One PermissionManagerWindow per APK, exactly like the CLI.

        PermissionManagerWindow is a frameless QWidget - it has no exec();
        show it and spin a QEventLoop that the result_ready signal quits
        (same pattern as install_as_system_app).
        """
        profiles = {}
        for apk_path in apk_paths:
            try:
                info = ApkAnalyzer.get_all_info(apk_path)
            except Exception as exc:
                self._err(f"Cannot read {os.path.basename(apk_path)}:\n{exc}")
                return None
            box = [None]
            loop = QEventLoop()
            dlg = PermissionManagerWindow(
                package_name=info["package"], app_label=info["label"],
                parent=self)
            dlg._signals.result_ready.connect(
                lambda r, b=box, l=loop: (b.__setitem__(0, r), l.quit()))
            screen = QApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                dlg.move(
                    available.center().x() - dlg.width() // 2,
                    available.center().y() - dlg.height() // 2,
                )
            dlg.show()
            loop.exec()
            profile = box[0]
            profiles[info["package"]] = profile if profile is not None \
                else self._default_profile()
        return profiles

    def _cli_info(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            text = self._build_info_text()
        finally:
            QApplication.restoreOverrideCursor()
        dlg = InfoDialog(
            f"IMG Info \u2014 {os.path.basename(self._real_path)}", text, self)
        dlg.exec()

    def _build_info_text(self):
        """Full report for the live image: file facts, cpio census, recovery
        state, hook state, module images and WSA detection."""
        path = self._real_path
        lines = []

        def add(text=""):
            lines.append(text)

        add(f"File: {path}")
        try:
            size = os.path.getsize(path)
            add(f"Size: {size:,} bytes ({self._fmt_size(size)})")
            stamp = time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime(os.path.getmtime(path)))
            add(f"Modified: {stamp}")
        except OSError as exc:
            add(f"Stat failed: {exc}")
        add(f"SHA-256: {self._file_hash(path) or 'unavailable'}")
        add(f"Staged copy: {'differs (not applied)' if self._dirty else 'in sync'}")
        backups = self._backup_files()
        add(f"Backups: {len(backups)}" + (f" (latest {backups[-1]})" if backups else ""))
        add()

        try:
            rows = CpioUtils.list_entries(path)
        except Exception as exc:
            add(f"Format: not a readable cpio image ({exc})")
            return "\n".join(lines)

        n_dirs = n_files = n_links = 0
        unpacked = 0
        for _name, mode, size in rows:
            kind = mode & 0o170000
            if kind == 0o040000:
                n_dirs += 1
            elif kind == 0o120000:
                n_links += 1
            else:
                n_files += 1
                unpacked += size
        add("Format: cpio (newc)")
        add(f"Entries: {len(rows):,} "
            f"({n_dirs:,} folders \u00b7 {n_files:,} files \u00b7 {n_links:,} symlinks)")
        add(f"Unpacked size: {unpacked:,} bytes ({self._fmt_size(unpacked)})")
        add()

        initrd = InitrdManager(path)
        if initrd.is_stock():
            add("Recovery system: STOCK (no TWRP)")
        else:
            add("Recovery system: PRESENT")
            info = initrd.read_info()
            if info:
                for key in ("twrp_support", "gapp_support", "root_support",
                            "root_method", "amazon_support", "recovery_flag",
                            "build_version", "wsa_version"):
                    if key in info:
                        add(f"  {key}: {info[key]}")
                missing = initrd.twrp_missing()
                add(f"  missing TWRP files: "
                    f"{', '.join(missing) if missing else 'none'}")
                note = info.get("note", "")
                if note:
                    add(f"  note: {note}")
            else:
                add("  (no info.json)")
        add()

        if CpioUtils.has_file(path, POSTFSDATA_ARCNAME):
            issues = initrd.hook_issues()
            if issues:
                add(f"Magisk hook: installed, {len(issues)} problem(s)")
                for issue in issues:
                    add(f"  - {issue}")
            else:
                add("Magisk hook: installed, OK")
        else:
            add("Magisk hook: not installed")
        add()

        add("Module images (spec of the stock image \u2014 extract to see the "
            "live copy):")
        for spec in IMAGE_SPECS.values():
            arc = f"overlay.d/sbin/{spec['image']}"
            present = CpioUtils.has_file(path, arc)
            add(f"  {spec['label']}: {spec['image']} \u2014 "
                f"{'present' if present else 'not present'}")
            if present:
                add(f"    id={spec['mod_id']}  name={spec['mod_name']}")
        add()

        wsa = WSADetector.find_path()
        add(f"WSA: {wsa or 'not detected'}")
        if wsa:
            add(f"WSA running: {WSADetector.is_running()}")
            wsa_initrd = WSADetector.initrd_path(wsa)
            same = (os.path.normpath(wsa_initrd) == os.path.normpath(path))
            add(f"WSA initrd: {wsa_initrd}"
                + ("  (this file)" if same else ""))
        return "\n".join(lines)

    def _cli_install_app(self):
        self._cli_install_system_app(force_update=False)

    def _cli_update_app(self):
        self._cli_install_system_app(force_update=True)

    def _cli_install_system_app(self, force_update=False):
        mode = self._admin_gate()
        if mode is None:
            return
        what = "update system apps" if force_update else "install system apps"
        if not self._confirm_live(what):
            return
        paths, _filter = QFileDialog.getOpenFileNames(
            self, "Choose APK file(s) to add as system app", "",
            "Android packages (*.apk);;All files (*.*)")
        if not paths:
            return
        profiles = self._collect_profiles(paths)
        if profiles is None:
            return
        label = "Update system app" if force_update else "Install system app"
        dlg = LogDialog(f"{label} ({mode} module)", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_install_system_app, dict(
            apk_paths=list(paths),
            target_initrd=self._real_path,
            permission_profiles=profiles,
            force_update=force_update,
            mode=mode,
        ))
        dlg.show()

    def _cli_status(self):
        dlg = LogDialog("Status", self)
        dlg.run_printing(self._twrp.status, dict(initrd_path=self._real_path))
        dlg.show()

    def _cli_list_apps(self):
        dlg = LogDialog("System apps", self)
        dlg.run_printing(self._twrp.list_boltware,
                         dict(initrd_path=self._real_path))
        dlg.show()

    def _cli_uninstall_app(self):
        text, ok = QInputDialog.getText(
            self, "Uninstall system app",
            "Package name (e.g. com.example.app):")
        if not ok:
            return
        pkg = (text or "").strip()
        if not pkg:
            self._info("No package name entered \u2014 nothing to do.")
            return
        if not self._confirm(
                f"Remove {pkg} from the system apps?\n"
                "The removal is scheduled for the next boot."):
            return
        if not self._confirm_live("uninstall system apps"):
            return
        dlg = LogDialog(f"Uninstall system app \u2014 {pkg}", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_printing(self._twrp.uninstall_boltware, dict(
            apk_name=pkg, initrd_path=self._real_path))
        dlg.show()

    def _cli_enable(self):
        if not self._confirm_live("enable TWRP recovery"):
            return
        dlg = LogDialog("Enable TWRP recovery", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_enable, dict(target_initrd=self._real_path))
        dlg.show()

    def _cli_disable(self):
        if not self._confirm_live("disable TWRP recovery"):
            return
        dlg = LogDialog("Disable TWRP recovery", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_disable, dict(target_initrd=self._real_path))
        dlg.show()

    def _cli_install_hook(self):
        if not self._confirm_live("install the boot hook"):
            return
        dlg = LogDialog("Install Magisk hook", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_install_magisk_hook,
                     dict(target_initrd=self._real_path, force=False))
        dlg.show()

    def _cli_repair_hook(self):
        if not self._confirm_live("repair the boot hook"):
            return
        dlg = LogDialog("Repair Magisk hook", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_install_magisk_hook,
                     dict(target_initrd=self._real_path, force=True))
        dlg.show()

    def _cli_install_twrp(self):
        if not self._confirm_live("install TWRP recovery"):
            return
        dlg = LogDialog("Install TWRP recovery", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_install_twrp,
                     dict(target_initrd=self._real_path, force=False))
        dlg.show()

    def _cli_repair_twrp(self):
        if not self._confirm_live("repair TWRP recovery"):
            return
        dlg = LogDialog("Repair TWRP recovery", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_install_twrp,
                     dict(target_initrd=self._real_path, force=True))
        dlg.show()

    def _cli_uninstall_twrp(self):
        if not self._confirm(
                "Uninstall TWRP?\n\n"
                "Removes /sbin/twrp, /sbin/busybox, /sbin/linker64,\n"
                "/twres/, /etc/ and /system/lib64/, then sets\n"
                "twrp_support=false and recovery_flag=false in info.json."):
            return
        if not self._confirm_live("uninstall TWRP recovery"):
            return
        dlg = LogDialog("Uninstall TWRP recovery", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_uninstall_twrp,
                     dict(target_initrd=self._real_path))
        dlg.show()

    def _cli_uninstall_hook(self):
        if not self._confirm(
                "Uninstall the Magisk hook?\n\n"
                "/wsainit is renamed to /init; lspinit, magiskinit and the\n"
                "whole overlay.d/ tree (hook scripts + module images) are\n"
                "removed."):
            return
        if not self._confirm_live("uninstall the boot hook"):
            return
        dlg = LogDialog("Uninstall Magisk hook", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_uninstall_magisk_hook,
                     dict(target_initrd=self._real_path))
        dlg.show()

    def _cli_cleanup_uninstall(self):
        if not self._confirm_live("clean up the pending uninstall list"):
            return
        dlg = LogDialog("Uninstall temp cleanup", self)
        dlg.finished.connect(lambda _r: self._after_live_change())
        dlg.run_flow(self._twrp._flow_cleanup_uninstall,
                     dict(target_initrd=self._real_path))
        dlg.show()

    def _cli_register_img(self):
        dlg = LogDialog("Register .img handler", self)
        dlg.run_printing(register_img_handler, {})
        dlg.show()

    def _cli_unregister_img(self):
        if not self._confirm("Remove the .img right-click entries "
                             "(\"Open in WSA IMG Manager\")?"):
            return
        dlg = LogDialog("Unregister .img handler", self)
        dlg.run_printing(unregister_img_handler, {})
        dlg.show()

    def _on_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if item is not None and not item.isSelected():
            self._tree.clearSelection()
            self._tree.setCurrentItem(item)
            item.setSelected(True)
        menu = QMenu(self)
        for key, label in self._ACTIONS:
            action = menu.addAction(label)
            action.triggered.connect(lambda _checked=False, k=key: self._on_action(k))
            if key == "open":
                menu.addSeparator()
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _on_double_click(self, item, _column):
        data = item.data(0, Qt.UserRole)
        if data and data.get("dir"):
            return  # folders just expand
        self._act_open()

    def _act_refresh(self):
        self._last_action = "refreshed"
        self._reload()

    def _act_backup(self):
        """Snapshot the LIVE image (not the staged copy) next to it."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = f"{self._real_path}.bak-{stamp}"
        copy = 1
        while os.path.exists(dest):
            copy += 1
            dest = f"{self._real_path}.bak-{stamp}-{copy}"
        try:
            shutil.copy2(self._real_path, dest)
        except Exception as exc:
            self._err(f"Backup failed:\n{exc}")
            return
        self._refresh_buttons()
        self._last_action = f"backup -> {os.path.basename(dest)}"
        self._update_status()
        self._info(f"Backup written at {time.strftime('%H:%M:%S')}:\n{dest}")

    def _act_apply(self):
        """Atomically replace the live image with the staged one."""
        if not self._dirty:
            self._info("Nothing to apply \u2014 staged image matches the live one.")
            return
        if not self._confirm(
                "Write the staged image over the live one?\n"
                f"{os.path.basename(self._real_path)} will be replaced."):
            return
        if not self._backup_files():
            if self._confirm(
                    "There is NO backup of this image.\nCreate one before applying?"):
                self._act_backup()
                if not self._backup_files():
                    return
        temp = self._real_path + ".applied.tmp"
        try:
            shutil.copy2(self._path, temp)
            os.replace(temp, self._real_path)
        except Exception as exc:
            try:
                os.remove(temp)
            except OSError:
                pass
            self._err(f"Apply failed:\n{exc}")
            return
        self._real_hash = self._file_hash(self._real_path)
        self._update_dirty()
        self._refresh_buttons()
        self._last_action = "applied to live image"
        self._update_status()
        self._info(f"Applied:\n{self._real_path}")

    def _act_restore(self):
        """Replace the staged image with a saved backup (live image untouched)."""
        found = self._backup_files()
        if not found:
            self._info("No backups exist yet \u2014 press Backup first.")
            return
        folder = os.path.dirname(self._real_path) or "."
        name, ok = QInputDialog.getItem(
            self, "Restore backup", "Backup:", found, 0, False)
        if not ok or not name:
            return
        src = os.path.join(folder, name)
        if not self._confirm(
                f"Replace the staged image with\n{name}?\n"
                "The live image is not touched until you press Apply."):
            return
        try:
            shutil.copy2(src, self._path)
        except Exception as exc:
            self._err(f"Restore failed:\n{exc}")
            return
        self._mgr = InitrdManager(self._path)
        self._reset_history()
        self._last_action = f"restored {name} into staging"
        self._reload()
        self._refresh_buttons()
        self._info(f"Staged image replaced with:\n{src}")

    def _act_open(self):
        """Open one entry INSIDE the app: system image, archive or editor.

        Never opens a file dialog on its own initiative \u2014 an unknown
        binary asks first instead of dropping the user in a folder picker.
        """
        info = self._single_selection()
        if info is None:
            self._info("Select exactly one file entry to open.")
            return
        name, _mode, is_dir = info
        if is_dir:
            self._info("Folders cannot be opened \u2014 select a file.")
            return
        try:
            data = CpioUtils.read_file(self._path, name)
        except Exception as exc:
            self._err(f"Cannot read /{name}:\n{exc}")
            return
        if data is None:
            self._err(f"/{name} is no longer present in the image.")
            return

        if data[:4] == b"\x3a\xff\x26\xed":
            self._err(
                f"/{name} is an Android sparse image.\n"
                "Convert it with simg2img before opening.")
            return

        if name.lower().endswith(".img"):
            self._open_system_image(name, data)
            return

        if ArchiveViewerDialog.sniff(data, name) is not None:
            self._show_viewer(name, data)
            return

        if _looks_like_text(data):
            self._edit_text(name, data)
            return

        # unknown binary: the built-in decoders missed, let 7-Zip have a go
        self._show_viewer(name, data)

    def _commit_bytes(self, name, packed, verb="repacked"):
        """Write rebuilt archive bytes into the STAGED image, never the live one."""
        mode, _size = self._entries.get(name, (0, 0))
        perms = ((mode or 0o100644) | guess_mode(name, packed)) & 0o7777
        if self._commit_op(
                f"{verb} /{name} ({len(packed):,} bytes)",
                lambda: self._mgr.overwrite(name, packed,
                                            mode=0o100000 | perms)):
            self._info(f"Packed into the staged image:\n/{name}\n"
                       "Press Apply to write the live image.")
            return True
        return False

    def _show_viewer(self, name, data):
        """Open the archive viewer; on failure ask, never auto-open a picker."""
        viewer = ArchiveViewerDialog(name, data, self)
        if viewer.error():
            self._open_unknown(name, data, viewer.error())
            return False
        viewer.exec()
        packed = viewer.result_bytes()
        if packed:
            self._commit_bytes(name, packed, "rebuilt")
            return True
        self._last_action = f"viewed /{name}"
        self._update_status()
        return True

    def _open_system_image(self, name, data):
        """Internal .img -> img-checker extract, edit, img-creater pack."""
        dlg = NestedImgDialog(
            name, data, os.path.join(self._stage_dir, "nested"), self)
        if dlg.error():
            img_error = dlg.error()
            dlg.reject()
            viewer = ArchiveViewerDialog(name, data, self)
            if viewer.error():
                self._err(
                    f"/{name} could not be opened.\n\n"
                    f"img-checker.exe \u2014 {img_error}\n\n"
                    f"7-Zip \u2014 {viewer.error()}")
                return
            viewer.exec()
            packed = viewer.result_bytes()
            if packed:
                self._commit_bytes(name, packed, "rebuilt")
                return
            self._last_action = f"viewed /{name} (read-only)"
            self._update_status()
            return
        dlg.exec()
        packed = dlg.packed_bytes()
        if not packed:
            self._last_action = f"no changes packed into /{name}"
            self._update_status()
            return
        mode, _size = self._entries.get(name, (0, 0))
        new_mode = 0o100000 | ((mode or 0o100644) & 0o7777)
        if self._commit_op(
                f"repacked /{name} ({len(packed):,} bytes)",
                lambda: self._mgr.overwrite(name, packed, mode=new_mode)):
            self._info(f"Packed into the staged image:\n/{name}\n"
                       "Press Apply to write the live image.")

    def _edit_text(self, name, data):
        mode, _size = self._entries.get(name, (0, 0))
        dlg = ScriptEditorDialog(name, data, self)
        if dlg.exec() != QDialog.Accepted:
            return False
        payload = dlg.result_bytes()
        if payload == data:
            self._last_action = "no changes saved"
            self._update_status()
            return False
        new_mode = 0o100000 | ((mode | guess_mode(name, payload)) & 0o7777)
        if self._commit_op(
                f"saved /{name} ({len(payload):,} bytes)",
                lambda: self._mgr.overwrite(name, payload, mode=new_mode)):
            self._info(f"Saved to the staged image:\n/{name}\n"
                       "Press Apply to write the live image.")
            return True
        return False

    def _open_unknown(self, name, data, reason=""):
        """Ask what to do instead of popping a folder picker by itself."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("IMG Manager")
        box.setText(f"/{name} is not a recognised archive.")
        info = ("Nothing is extracted on its own. Open it as text, or save "
                "a copy to disk.")
        if reason:
            info = f"{reason}\n\n{info}"
        box.setInformativeText(info)
        text_btn = box.addButton("Open as text", QMessageBox.AcceptRole)
        save_btn = box.addButton("Save a copy\u2026", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(text_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is text_btn:
            self._edit_text(name, data)
            return
        if clicked is save_btn:
            dest, _filter = QFileDialog.getSaveFileName(
                self, f"Save a copy of {name}", name.rpartition("/")[2])
            if not dest:
                return
            try:
                with open(dest, "wb") as handle:
                    handle.write(data)
            except OSError as exc:
                self._err(f"Save failed:\n{exc}")
                return
            self._last_action = f"saved a copy of /{name}"
            self._update_status()
            self._info(f"Saved a copy to:\n{dest}")

    def _act_extract(self):
        names = self._selected() or None
        if names is None:
            if not self._confirm("No selection \u2014 extract the whole image?"):
                return
        dest = QFileDialog.getExistingDirectory(self, "Extract to folder")
        if not dest:
            return
        try:
            count = self._mgr.extract(dest, names)
        except Exception as exc:
            self._err(f"Extract failed:\n{exc}")
            return
        self._last_action = f"extracted {count} entries"
        self._reload()
        self._info(f"Extracted {count} entries to:\n{dest}")

    def _act_delete(self):
        names = self._selected()
        if not names:
            self._info("Select one or more entries to delete.")
            return
        total = sum(1 for key in self._entries
                    if any(key == n or key.startswith(n + "/") for n in names))
        word = "entry" if len(names) == 1 else "entries"
        if not self._confirm(f"Delete {len(names)} selected {word}?\n"
                             f"This removes {total} entries from the image."):
            return
        self._commit_op(
            f"deleted {total} entries",
            lambda: self._mgr.delete_entries(names))

    def _act_rename(self):
        info = self._single_selection()
        if info is None:
            self._info("Select exactly one entry to rename.")
            return
        old, _mode, _is_dir = info
        current = old.rpartition("/")[2]
        text, ok = QInputDialog.getText(self, "IMG Manager", "New name:", text=current)
        if not ok:
            return
        new_base = text.strip()
        if not self._valid_name(new_base):
            if new_base:
                self._err("Invalid name: no slashes, backslashes or dots.")
            return
        parent = old.rpartition("/")[0]
        new = f"{parent}/{new_base}" if parent else new_base
        if new == old:
            return
        self._commit_op(
            f"renamed {old} -> {new}",
            lambda: self._mgr.rename(old, new))

    def _act_overwrite(self):
        info = self._single_selection()
        if info is None:
            self._info("Select exactly one file entry to overwrite.")
            return
        old, mode, is_dir = info
        if is_dir:
            self._err("Cannot overwrite a folder from disk \u2014 use Add Folder instead.")
            return
        src, _filter = QFileDialog.getOpenFileName(
            self, f"Replace /{old} with file\u2026")
        if not src:
            return
        try:
            with open(src, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            self._err(f"Cannot read {src}:\n{exc}")
            return
        new_mode = 0o100000 | ((mode | guess_mode(old, data)) & 0o7777)
        self._commit_op(
            f"overwrote /{old} ({len(data):,} bytes)",
            lambda: self._mgr.overwrite(old, data, mode=new_mode))

    def _act_add_file(self):
        dest = self._dest_for_add()
        src, _filter = QFileDialog.getOpenFileName(self, "Add file to image")
        if not src:
            return
        arcname = f"{dest}/{os.path.basename(src)}" if dest else os.path.basename(src)
        if arcname in self._entries and not self._confirm(f"/{arcname} already exists.\nReplace it?"):
            return
        self._commit_op(
            f"added /{arcname}",
            lambda: self._mgr.inject_file(src, dest=dest))

    def _act_add_folder(self):
        dest = self._dest_for_add()
        src = QFileDialog.getExistingDirectory(self, "Add folder to image")
        if not src:
            return
        base = os.path.basename(os.path.normpath(src))
        if not base:
            self._err("Cannot determine the folder name.")
            return
        root = f"{dest}/{base}" if dest else base
        if root in self._entries:
            if not self._confirm(f"/{root} already exists.\nReplace it?"):
                return
        def _add_folder():
            if root in self._entries:
                CpioUtils.delete_tree(self._path, root)
            self._mgr.inject_folder(src, dest=root)
        self._commit_op(f"added folder /{root}", _add_folder)

    def _act_new_folder(self):
        dest = self._dest_for_add()
        text, ok = QInputDialog.getText(self, "IMG Manager", "New folder name:")
        if not ok:
            return
        name = text.strip().strip("/")
        if not self._valid_name(name):
            if name:
                self._err("Invalid name: no slashes, backslashes or dots.")
            return
        arcname = f"{dest}/{name}" if dest else name
        self._commit_op(
            f"created folder /{arcname}",
            lambda: self._mgr.new_folder(arcname))

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key_Z, Qt.Key_Y) and (mods & Qt.ControlModifier):
            if key == Qt.Key_Y or (mods & Qt.ShiftModifier):
                self._redo()
            else:
                self._undo()
            event.accept()
            return
        handlers = {
            Qt.Key_Delete: "delete",
            Qt.Key_F2: "rename",
            Qt.Key_F5: "refresh",
        }
        action = handlers.get(key)
        if action is not None and mods == Qt.NoModifier:
            self._on_action(action)
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._dirty:
            answer = QMessageBox.question(
                self, "IMG Manager",
                "You have staged edits that were never applied.\n"
                "Discard them and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()
        shutil.rmtree(self._stage_dir, ignore_errors=True)


class WSATWRP:

    def __init__(self):
        self.wsa_path = None
        self.adb = ADBManager()

    def _cleanup(self):
        pass

    def _launch_gui(self, flow_func, flow_args=None):
        if flow_args is None:
            flow_args = {}
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setStyle("Fusion")

        window = RecoveryWindow()
        screen = app.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            window.move(
                available.center().x() - window.width() // 2,
                available.center().y() - window.height() // 2,
            )
        window.show()

        def log(msg):
            print(f"  {msg}", flush=True)
            window.update_log(msg)

        def run_flow():
            try:
                print(f"\n[{APP_NAME} v{APP_VERSION}]", flush=True)
                print("=" * 50, flush=True)
                flow_func(log, window, **flow_args)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                log(f"Error: {e}")
                time.sleep(2)
                window.request_close()

        thread = threading.Thread(target=run_flow, daemon=True)
        QTimer.singleShot(200, thread.start)
        result = app.exec()
        self._cleanup()
        return result

    def boot_to_twrp(self, target_initrd=None, inject_file=None, inject_folder=None,
                      inject_7z=None, inject_dest="/"):
        return self._launch_gui(self._flow, dict(
            target_initrd=target_initrd,
            inject_file=inject_file,
            inject_folder=inject_folder,
            inject_7z=inject_7z,
            inject_dest=inject_dest,
        ))

    def enable_twrp(self, initrd_path=None):
        return self._launch_gui(self._flow_enable, dict(
            target_initrd=initrd_path,
        ))

    def disable_twrp(self, initrd_path=None):
        return self._launch_gui(self._flow_disable, dict(
            target_initrd=initrd_path,
        ))

    def install_twrp(self, initrd_path=None):
        return self._launch_gui(self._flow_install_twrp, dict(
            target_initrd=initrd_path,
            force=False,
        ))

    def repair_twrp(self, initrd_path=None):
        return self._launch_gui(self._flow_install_twrp, dict(
            target_initrd=initrd_path,
            force=True,
        ))

    def uninstall_twrp(self, initrd_path=None):
        return self._launch_gui(self._flow_uninstall_twrp, dict(
            target_initrd=initrd_path,
        ))

    def _flow(self, log, window, target_initrd=None, inject_file=None,
              inject_folder=None, inject_7z=None, inject_dest="/"):
        _debug(f"_flow() started")
        _debug(f"  target_initrd: {target_initrd}")
        _debug(f"  inject_file: {inject_file}")
        _debug(f"  inject_folder: {inject_folder}")
        _debug(f"  inject_7z: {inject_7z}")
        _debug(f"  inject_dest: {inject_dest}")

        # [1] Detect WSA or use provided path
        is_wsa_img = False
        if target_initrd:
            _debug(f"  --path provided: {target_initrd}")
            initrd_path = target_initrd
            if not os.path.exists(initrd_path):
                log(f"File not found: {initrd_path}")
                time.sleep(2)
                window.request_close()
                return
            fsize = os.path.getsize(initrd_path)
            log(f"File: {os.path.basename(initrd_path)} ({fsize:,} bytes)")
            time.sleep(0.5)

            wsa_path = WSADetector.find_path()
            if wsa_path:
                wsa_initrd = WSADetector.initrd_path(wsa_path)
                _debug(f"  WSA initrd: {wsa_initrd}")
                _debug(f"  --path:     {initrd_path}")
                if os.path.normpath(initrd_path) == os.path.normpath(wsa_initrd):
                    is_wsa_img = True
                    _debug(f"  --path IS the WSA img -> need kill/restart")
                    log(f"Detected: WSA recovery system")
                else:
                    _debug(f"  --path is NOT the WSA img -> direct patch only")
                    log(f"Detected: external file (not WSA)")
            else:
                _debug(f"  WSA not installed -> direct patch only")
                log(f"Detected: standalone file (no WSA)")
        else:
            log("Checking WSA installation...")
            time.sleep(1)
            self.wsa_path = WSADetector.find_path()
            if not self.wsa_path:
                log("WSA not found!")
                time.sleep(2)
                window.request_close()
                return
            log(f"WSA found: {os.path.basename(self.wsa_path)}")
            initrd_path = WSADetector.initrd_path(self.wsa_path)
            if not os.path.exists(initrd_path):
                log("Recovery system not found!")
                time.sleep(2)
                window.request_close()
                return
            is_wsa_img = True
        time.sleep(0.5)

        initrd = InitrdManager(initrd_path)
        has_twrp = initrd.is_twrp_supported()
        has_inject = inject_file or inject_folder or inject_7z
        _debug(f"  has_twrp: {has_twrp}")
        _debug(f"  has_inject: {has_inject}")

        if not has_twrp:
            _debug("  Branch: FIRST_TIME_INSTALL")
            # First time install
            missing = initrd.twrp_missing()
            if missing:
                log(f"TWRP files missing: {', '.join(missing)}")
            log("Installing TWRP...")
            time.sleep(0.5)

            if is_wsa_img:
                log("Stopping WSA...")
                KillWSA.kill_all()
                time.sleep(3)
            else:
                _debug("  Skipping WSA kill (not WSA img)")
                log("Patching file directly...")

            log("Checking Magisk hook...")
            hook_problems = initrd.hook_issues()
            if hook_problems:
                for problem in hook_problems:
                    log(f"  - {problem}")
                initrd.add_hook_infrastructure()
                initrd.repair_hook_infrastructure()
                hook_problems = initrd.hook_issues()
                if hook_problems:
                    log("Magisk hook install failed:")
                    for problem in hook_problems:
                        log(f"  - {problem}")
                    time.sleep(2)
                    window.request_close()
                    return
                log("Magisk hook installed")
            else:
                log("Magisk hook already present")
            time.sleep(0.5)

            if inject_file:
                log(f"Injecting file: {os.path.basename(inject_file)} -> {inject_dest}")
                if not os.path.exists(inject_file):
                    log(f"File not found: {inject_file}")
                    time.sleep(2)
                    window.request_close()
                    return
                initrd.inject_file(inject_file, inject_dest)

            elif inject_folder:
                log(f"Injecting folder: {os.path.basename(inject_folder)} -> {inject_dest}")
                if not os.path.isdir(inject_folder):
                    log(f"Folder not found: {inject_folder}")
                    time.sleep(2)
                    window.request_close()
                    return
                initrd.inject_folder(inject_folder, inject_dest)

            elif inject_7z:
                log(f"Injecting 7z: {os.path.basename(inject_7z)} -> {inject_dest}")
                if not os.path.exists(inject_7z):
                    log(f"7z not found: {inject_7z}")
                    time.sleep(2)
                    window.request_close()
                    return
                initrd.inject_7z_with_patch(inject_7z, inject_dest)

            else:
                log(f"Auto-injecting: {os.path.basename(ASSET_TWRP_7Z)}")
                if not os.path.exists(ASSET_TWRP_7Z):
                    log("TWRP recovery file not found!")
                    time.sleep(2)
                    window.request_close()
                    return
                initrd.inject_7z_with_patch(ASSET_TWRP_7Z, inject_dest)

            initrd = InitrdManager(initrd_path)
            if not initrd.has_info_json():
                log("Injection failed!")
                time.sleep(2)
                window.request_close()
                return
            log("TWRP installed")
            time.sleep(0.5)

            if is_wsa_img:
                log("Starting WSA...")
                WSADetector.ensure_running()
                time.sleep(15)

                initrd = InitrdManager(initrd_path)
                if initrd.is_stock():
                    log("Installation failed!")
                    time.sleep(2)
                    window.request_close()
                    return
            else:
                _debug("  Skipping WSA restart (not WSA img)")
                log("Patch complete!")
                time.sleep(1)
                window.request_close()
                return

        elif has_inject:
            _debug("  Branch: OVERRIDE")
            # Already installed but --inject* specified -> override
            log("Overriding existing recovery system...")
            time.sleep(0.5)

            if is_wsa_img:
                log("Stopping WSA...")
                KillWSA.kill_all()
                time.sleep(3)
            else:
                _debug("  Skipping WSA kill (not WSA img)")
                log("Patching file directly...")

            if inject_file:
                log(f"Overriding file: {os.path.basename(inject_file)} -> {inject_dest}")
                if not os.path.exists(inject_file):
                    log(f"File not found: {inject_file}")
                    time.sleep(2)
                    window.request_close()
                    return
                initrd.inject_file(inject_file, inject_dest)

            elif inject_folder:
                log(f"Overriding folder: {os.path.basename(inject_folder)} -> {inject_dest}")
                if not os.path.isdir(inject_folder):
                    log(f"Folder not found: {inject_folder}")
                    time.sleep(2)
                    window.request_close()
                    return
                initrd.inject_folder(inject_folder, inject_dest)

            elif inject_7z:
                log(f"Overriding 7z: {os.path.basename(inject_7z)} -> {inject_dest}")
                if not os.path.exists(inject_7z):
                    log(f"7z not found: {inject_7z}")
                    time.sleep(2)
                    window.request_close()
                    return
                initrd.inject_7z_with_patch(inject_7z, inject_dest)

            log("Override complete")
            time.sleep(0.5)

            if not is_wsa_img:
                _debug("  Skipping WSA restart (not WSA img)")
                log("Patch complete!")
                time.sleep(1)
                window.request_close()
                return

        else:
            _debug("  Branch: ALREADY_INSTALLED")
            log("TWRP already installed")
            time.sleep(0.5)

        if not initrd.is_twrp_supported():
            log("Recovery system does not support TWRP!")
            time.sleep(2)
            window.request_close()
            return

        # [4] Check/set recovery flag
        flag = initrd.get_recovery_flag()
        if flag:
            log("TWRP mode already active")
        else:
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)

            log("Activating TWRP mode...")
            initrd.set_recovery_flag(True)
            log("Recovery mode: ACTIVE")
            time.sleep(0.5)

        # [5] Start WSA (loads modified initrd -> TWRP boots)
        log("Starting WSA...")
        WSADetector.ensure_running()

        # [6] Wait for TWRP
        log("Waiting for TWRP...")
        self.adb.wait_for_recovery()

        # [7] Clear recovery flag
        log("Restoring normal boot...")
        initrd.set_recovery_flag(False)
        log("Recovery mode: INACTIVE")
        time.sleep(0.5)

        # [8] Success
        log("TWRP Ready!")
        print("\n  TWRP is running in WSA. Tool will close now.", flush=True)
        time.sleep(2)

        window.request_close()

    @staticmethod
    def _resolve_initrd(log, window, target_initrd):
        """Shared head of the TWRP/hook flows: locate the image and decide
        whether it is the live WSA one. Returns (path, is_wsa_img), or None
        after reporting the problem and closing the dialog."""
        is_wsa_img = False
        if target_initrd:
            initrd_path = target_initrd
            if not os.path.exists(initrd_path):
                log(f"File not found: {initrd_path}")
                time.sleep(2)
                window.request_close()
                return None
            log(f"File: {os.path.basename(initrd_path)} "
                f"({os.path.getsize(initrd_path):,} bytes)")
            wsa_path = WSADetector.find_path()
            if wsa_path:
                if os.path.normpath(initrd_path) == os.path.normpath(
                        WSADetector.initrd_path(wsa_path)):
                    is_wsa_img = True
                    log("Detected: WSA recovery system")
                else:
                    log("Detected: external file (not WSA)")
            else:
                log("Detected: standalone file (no WSA)")
        else:
            log("Checking WSA installation...")
            time.sleep(1)
            wsa_path = WSADetector.find_path()
            if not wsa_path:
                log("WSA not found!")
                time.sleep(2)
                window.request_close()
                return None
            log(f"WSA found: {os.path.basename(wsa_path)}")
            initrd_path = WSADetector.initrd_path(wsa_path)
            if not os.path.exists(initrd_path):
                log("Recovery system not found!")
                time.sleep(2)
                window.request_close()
                return None
            is_wsa_img = True
        time.sleep(0.5)
        return initrd_path, is_wsa_img

    def _flow_enable(self, log, window, target_initrd=None):
        _debug("_flow_enable() started")
        is_wsa_img = False

        if target_initrd:
            initrd_path = target_initrd
            _debug(f"  --path provided: {initrd_path}")
            if not os.path.exists(initrd_path):
                log(f"File not found: {initrd_path}")
                time.sleep(2)
                window.request_close()
                return
            fsize = os.path.getsize(initrd_path)
            log(f"File: {os.path.basename(initrd_path)} ({fsize:,} bytes)")
            wsa_path = WSADetector.find_path()
            if wsa_path:
                wsa_initrd = WSADetector.initrd_path(wsa_path)
                if os.path.normpath(initrd_path) == os.path.normpath(wsa_initrd):
                    is_wsa_img = True
                    log("Detected: WSA recovery system")
                else:
                    log("Detected: external file (not WSA)")
            else:
                log("Detected: standalone file (no WSA)")
        else:
            log("Checking WSA installation...")
            time.sleep(1)
            wsa_path = WSADetector.find_path()
            if not wsa_path:
                log("WSA not found!")
                time.sleep(2)
                window.request_close()
                return
            log(f"WSA found: {os.path.basename(wsa_path)}")
            initrd_path = WSADetector.initrd_path(wsa_path)
            is_wsa_img = True

        if not os.path.exists(initrd_path):
            log(f"Recovery system not found: {initrd_path}")
            time.sleep(2)
            window.request_close()
            return
        time.sleep(0.5)

        initrd = InitrdManager(initrd_path)
        if initrd.is_stock():
            log("Stock WSA (no recovery system installed)")
            log(f"Run {CLI_NAME} without --enable-twrp to install first")
            time.sleep(2)
            window.request_close()
            return
        if not initrd.get_twrp_support():
            log("TWRP is NOT installed (twrp_support = false)")
            log(f"Run {CLI_NAME} --install-twrp first (or press "
                "'Install TWRP' in the manager)")
            time.sleep(2)
            window.request_close()
            return
        missing = initrd.twrp_missing()
        if missing:
            log("TWRP install is incomplete - missing:")
            for item in missing:
                log(f"  - {item}")
            log(f"Run {CLI_NAME} --repair-twrp first (or press 'Repair TWRP')")
            time.sleep(2)
            window.request_close()
            return
        if initrd.get_recovery_flag():
            log("Recovery mode already ON")
            time.sleep(1)
            window.request_close()
            return

        log("Enabling recovery mode...")
        time.sleep(0.5)
        if is_wsa_img and WSADetector.is_running():
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        initrd.set_recovery_flag(True)
        log("Recovery mode: ON")
        time.sleep(0.5)

        if is_wsa_img:
            log("Starting WSA...")
            WSADetector.ensure_running()
            time.sleep(15)
            log("Done! TWRP will boot on next restart.")
        else:
            log("Done!")
        time.sleep(1)
        window.request_close()

    def _flow_disable(self, log, window, target_initrd=None):
        _debug("_flow_disable() started")
        is_wsa_img = False

        if target_initrd:
            initrd_path = target_initrd
            _debug(f"  --path provided: {initrd_path}")
            if not os.path.exists(initrd_path):
                log(f"File not found: {initrd_path}")
                time.sleep(2)
                window.request_close()
                return
            fsize = os.path.getsize(initrd_path)
            log(f"File: {os.path.basename(initrd_path)} ({fsize:,} bytes)")
            wsa_path = WSADetector.find_path()
            if wsa_path:
                wsa_initrd = WSADetector.initrd_path(wsa_path)
                if os.path.normpath(initrd_path) == os.path.normpath(wsa_initrd):
                    is_wsa_img = True
                    log("Detected: WSA recovery system")
                else:
                    log("Detected: external file (not WSA)")
            else:
                log("Detected: standalone file (no WSA)")
        else:
            log("Checking WSA installation...")
            time.sleep(1)
            wsa_path = WSADetector.find_path()
            if not wsa_path:
                log("WSA not found!")
                time.sleep(2)
                window.request_close()
                return
            log(f"WSA found: {os.path.basename(wsa_path)}")
            initrd_path = WSADetector.initrd_path(wsa_path)
            is_wsa_img = True

        if not os.path.exists(initrd_path):
            log(f"Recovery system not found: {initrd_path}")
            time.sleep(2)
            window.request_close()
            return
        time.sleep(0.5)

        initrd = InitrdManager(initrd_path)
        if initrd.is_stock():
            log("Stock WSA (no recovery system installed)")
            time.sleep(2)
            window.request_close()
            return
        if not initrd.get_recovery_flag():
            log("Recovery mode already OFF")
            time.sleep(1)
            window.request_close()
            return

        log("Disabling recovery mode...")
        time.sleep(0.5)
        if is_wsa_img and WSADetector.is_running():
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        initrd.set_recovery_flag(False)
        log("Recovery mode: OFF")
        time.sleep(0.5)

        if is_wsa_img:
            log("Starting WSA...")
            WSADetector.ensure_running()
            time.sleep(15)
            log("Done! Normal boot restored.")
        else:
            log("Done!")
        time.sleep(1)
        window.request_close()

    def _flow_install_twrp(self, log, window, target_initrd=None, force=False):
        _debug(f"_flow_install_twrp(force={force}) started")
        resolved = self._resolve_initrd(log, window, target_initrd)
        if resolved is None:
            return
        initrd_path, is_wsa_img = resolved

        initrd = InitrdManager(initrd_path)
        if initrd.is_stock():
            log("Stock WSA (no recovery system installed)")
            log(f"Run {CLI_NAME} without --install-twrp to install first")
            time.sleep(2)
            window.request_close()
            return

        flag_before = initrd.get_twrp_support()
        missing_before = initrd.twrp_missing()
        log(f"twrp_support: {'true' if flag_before else 'false'}")
        if missing_before:
            log(f"TWRP files missing: {', '.join(missing_before)}")
        if flag_before and not missing_before and not force:
            log("TWRP already installed, nothing to do")
            log("")
            log(f"To boot TWRP: {CLI_NAME} --enable-twrp")
            time.sleep(2)
            window.request_close()
            return

        if is_wsa_img:
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        else:
            log("Patching file directly...")

        if os.path.exists(ASSET_TWRP_7Z):
            log(f"Injecting: {os.path.basename(ASSET_TWRP_7Z)}")
            try:
                initrd.inject_7z_with_patch(ASSET_TWRP_7Z, "/")
            except RuntimeError as exc:
                log(f"Payload skipped: {exc}")
        else:
            log(f"{os.path.basename(ASSET_TWRP_7Z)} not found - "
                "updating info.json only")

        initrd = InitrdManager(initrd_path)
        initrd.set_twrp_support(True)
        initrd = InitrdManager(initrd_path)
        now_flag = initrd.get_twrp_support()
        log(f"twrp_support: {'true' if flag_before else 'false'} -> "
            f"{'true' if now_flag else 'false'}")
        if not now_flag:
            log("WARNING: twrp_support key missing or could not be written")
        missing_after = initrd.twrp_missing()
        if missing_after:
            log("WARNING: TWRP still incomplete - missing:")
            for item in missing_after:
                log(f"  - {item}")
            log("Fill assets/twrp.7z with a real payload and run --repair-twrp")
        else:
            log("TWRP installed successfully!")
            log(f"Next: {CLI_NAME} --enable-twrp")

        if is_wsa_img:
            log("Starting WSA...")
            WSADetector.ensure_running()
            time.sleep(15)
        else:
            log("Patch complete!")
        time.sleep(1)
        window.request_close()

    def _flow_uninstall_twrp(self, log, window, target_initrd=None):
        _debug("_flow_uninstall_twrp() started")
        resolved = self._resolve_initrd(log, window, target_initrd)
        if resolved is None:
            return
        initrd_path, is_wsa_img = resolved

        initrd = InitrdManager(initrd_path)
        if initrd.is_stock():
            log("Stock WSA - nothing to uninstall")
            time.sleep(2)
            window.request_close()
            return

        present = {name for name, *_ in CpioUtils.scan_entries(initrd_path)}
        files_here = [
            f"/{name.strip('/')}" for name in TWRP_REQUIRED_FILES
            if name.strip("/") != "info.json" and name.strip("/") in present]
        dirs_here = [
            name.strip("/") + "/" for name in TWRP_REQUIRED_DIRS
            if any(n.startswith(name.strip("/") + "/") for n in present)]
        flag_before = initrd.get_twrp_support()
        recovery_before = initrd.get_recovery_flag()
        if not flag_before and not files_here and not dirs_here:
            log("TWRP is not installed - nothing to remove")
            time.sleep(2)
            window.request_close()
            return

        log(f"twrp_support: {'true' if flag_before else 'false'}")
        log(f"recovery_flag: {'true' if recovery_before else 'false'}")
        if is_wsa_img:
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        else:
            log("Patching file directly...")

        log("Removing TWRP files...")
        for name in ("sbin/twrp", "sbin/busybox", "sbin/linker64"):
            if name in present:
                CpioUtils.delete_file(initrd_path, name)
                log(f"  removed /{name}")
            else:
                log(f"  skipped /{name} (not present)")
        for name in ("twres", "etc", "system/lib64"):
            hits = [n for n in present
                    if n == name or n.startswith(name + "/")]
            if hits:
                CpioUtils.delete_tree(initrd_path, name)
                log(f"  removed /{name}/ ({len(hits)} entries)")
            else:
                log(f"  skipped /{name}/ (not present)")

        # the payload ships the dispatcher as /init; without TWRP it must not
        # stay in front of the boot chain - fall back to lspinit when present
        init_mode = next(
            (m for n, m, _s in CpioUtils.list_entries(initrd_path)
             if n == "init"), None)
        if init_mode is not None and (init_mode & 0o170000) != 0o120000:
            if "lspinit" in present:
                CpioUtils.delete_file(initrd_path, "init")
                CpioUtils.add_symlink(initrd_path, "init", "lspinit")
                log("  /init: dispatcher -> init -> lspinit")
            else:
                log("  kept /init (no lspinit to fall back to)")
        elif init_mode is None:
            log("  /init not present (nothing to swap)")
        else:
            log("  /init already a symlink (kept)")

        initrd = InitrdManager(initrd_path)
        initrd.set_twrp_support(False)
        if recovery_before:
            initrd.set_recovery_flag(False)
        initrd = InitrdManager(initrd_path)
        now_flag = initrd.get_twrp_support()
        now_recovery = initrd.get_recovery_flag()
        log(f"twrp_support: {'true' if flag_before else 'false'} -> "
            f"{'true' if now_flag else 'false'}")
        log(f"recovery_flag: {'true' if recovery_before else 'false'} -> "
            f"{'true' if now_recovery else 'false'}")
        if not now_flag and not now_recovery:
            log("TWRP uninstalled")
        else:
            log("WARNING: flags could not be cleared completely")

        if is_wsa_img:
            log("Starting WSA...")
            WSADetector.ensure_running()
            time.sleep(15)
        else:
            log("Patch complete!")
        time.sleep(1)
        window.request_close()

    def install_as_system_app(self, apk_paths, target_initrd=None, force_update=False, mode=None):
        mode = resolve_mode(mode, "user")
        if mode == "admin" and not _require_admin_password():
            return 1
        select_image(mode)

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setStyle("Fusion")

        for apk_path in apk_paths:
            if not os.path.exists(apk_path):
                print(f"  File not found: {apk_path}", flush=True)
                return 1

        is_wsa_img = False
        if target_initrd:
            initrd_path = target_initrd
            if not os.path.exists(initrd_path):
                print(f"  File not found: {initrd_path}", flush=True)
                return 1
            wsa_path = WSADetector.find_path()
            if wsa_path:
                wsa_initrd = WSADetector.initrd_path(wsa_path)
                if os.path.normpath(initrd_path) == os.path.normpath(wsa_initrd):
                    is_wsa_img = True
        else:
            self.wsa_path = WSADetector.find_path()
            if not self.wsa_path:
                print("  WSA not found!", flush=True)
                return 1
            initrd_path = WSADetector.initrd_path(self.wsa_path)
            if not os.path.exists(initrd_path):
                print("  Recovery system not found!", flush=True)
                return 1
            is_wsa_img = True

        apk_infos = []
        for apk_path in apk_paths:
            info = ApkAnalyzer.get_all_info(apk_path)
            apk_infos.append(info)

        permission_profiles = {}
        for info in apk_infos:
            result_box = [None]
            loop = QEventLoop()
            dlg = PermissionManagerWindow(
                package_name=info["package"],
                app_label=info["label"],
            )
            dlg._signals.result_ready.connect(lambda r, rb=result_box, l=loop: (rb.__setitem__(0, r), l.quit()))
            screen = app.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                dlg.move(
                    available.center().x() - dlg.width() // 2,
                    available.center().y() - dlg.height() // 2,
                )
            dlg.show()
            loop.exec()
            profile = result_box[0]
            if profile is None:
                profile = {
                    "hide_uninstall": True,
                    "hide_disable": True,
                    "privapp_perms": sorted(PRIVILEGED_PERMS),
                    "runtime_perms": list(DANGEROUS_PERMS) + list(SPECIAL_PERMS),
                    "fixed_runtime_perms": list(DANGEROUS_PERMS) + list(SPECIAL_PERMS),
                }
            permission_profiles[info["package"]] = profile

        return self._launch_gui(self._flow_install_system_app, dict(
            apk_paths=apk_paths,
            target_initrd=target_initrd,
            permission_profiles=permission_profiles,
            force_update=force_update,
            mode=mode,
        ))

    def _flow_install_system_app(self, log, window, apk_paths, target_initrd=None,
                                  permission_profiles=None, force_update=False, mode=None):
        _debug("_flow_install_system_app() started")
        _debug(f"  apk_paths: {apk_paths}")
        mode = resolve_mode(mode, "user")
        select_image(mode)
        _debug(f"  module: {LSP_LABEL} -> {LSP_IMAGE_NAME} (id={LSP_MOD_ID})")

        for apk_path in apk_paths:
            if not os.path.exists(apk_path):
                log(f"File not found: {apk_path}")
                time.sleep(2)
                window.request_close()
                return

        is_wsa_img = False
        if target_initrd:
            _debug(f"  --path provided: {target_initrd}")
            initrd_path = target_initrd
            if not os.path.exists(initrd_path):
                log(f"File not found: {initrd_path}")
                time.sleep(2)
                window.request_close()
                return
            fsize = os.path.getsize(initrd_path)
            log(f"File: {os.path.basename(initrd_path)} ({fsize:,} bytes)")
            wsa_path = WSADetector.find_path()
            if wsa_path:
                wsa_initrd = WSADetector.initrd_path(wsa_path)
                if os.path.normpath(initrd_path) == os.path.normpath(wsa_initrd):
                    is_wsa_img = True
                    log("Detected: WSA recovery system")
                else:
                    log("Detected: external file (not WSA)")
            else:
                log("Detected: standalone file (no WSA)")
        else:
            log("Checking WSA installation...")
            time.sleep(1)
            self.wsa_path = WSADetector.find_path()
            if not self.wsa_path:
                log("WSA not found!")
                time.sleep(2)
                window.request_close()
                return
            log(f"WSA found: {os.path.basename(self.wsa_path)}")
            initrd_path = WSADetector.initrd_path(self.wsa_path)
            if not os.path.exists(initrd_path):
                log("Recovery system not found!")
                time.sleep(2)
                window.request_close()
                return
            is_wsa_img = True
        time.sleep(0.5)

        initrd = InitrdManager(initrd_path)

        if permission_profiles is None:
            permission_profiles = {}

        log("Installing system apps...")
        log(f"Module: {LSP_MOD_ID} ({LSP_LABEL}) - image {LSP_IMAGE_NAME}")
        for pkg, profile in permission_profiles.items():
            log(f"  {pkg}: privapp={len(profile.get('privapp_perms', []))}, "
                f"runtime={len(profile.get('runtime_perms', []))}")
        time.sleep(0.5)

        has_root = WSADetector.check_root()
        log(f"Root access: {'detected' if has_root else 'not detected'}")
        time.sleep(0.5)

        _debug("READ-ONLY PHASE: checking hooks and APKs")
        hook_ok = initrd.add_hook_infrastructure()
        if not hook_ok:
            log("Failed to add hook infrastructure!")
            time.sleep(2)
            window.request_close()
            return
        time.sleep(0.5)

        apks_to_write = []
        for apk_path in apk_paths:
            pkg = ApkAnalyzer.get_package_name(apk_path)
            profile = permission_profiles.get(pkg)
            if not profile:
                log(f"Skipped {pkg} (no profile)")
                continue
            if initrd.has_lsp_image():
                existing = initrd.find_existing_apks()
                apk_basename = os.path.basename(apk_path)
                found = any(os.path.basename(a) == apk_basename for _, a in existing)
                if found:
                    if force_update:
                        log(f"{pkg} already installed, updating")
                    else:
                        log(f"{pkg} already installed. Use {CLI_NAME} --update-as-system-app to reinstall.")
                        continue
            apks_to_write.append((apk_path, pkg, profile))

        if not apks_to_write:
            log("Nothing to install, all up to date")
            time.sleep(2)
            window.request_close()
            return

        _debug(f"WRITE PHASE: {len(apks_to_write)} app(s) to install")
        if is_wsa_img:
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        else:
            log("Patching file directly...")

        for apk_path, pkg, profile in apks_to_write:
            log(f"Installing {pkg} as system app")
            time.sleep(0.5)

            if initrd.has_lsp_image():
                _debug("Extracting existing image")
                extract_dir = initrd.extract_lsp_image()
                if extract_dir:
                    _debug(f"  extract_dir: {extract_dir}")
                    priv_app = os.path.join(extract_dir, "system", "priv-app")
                    os.makedirs(os.path.join(priv_app, pkg), exist_ok=True)
                    shutil.copy2(apk_path, os.path.join(priv_app, pkg, os.path.basename(apk_path)))
                    _debug(f"  Added: system/priv-app/{pkg}/{os.path.basename(apk_path)}")

                    perm_dir = os.path.join(extract_dir, "permissions")
                    os.makedirs(perm_dir, exist_ok=True)
                    with open(os.path.join(perm_dir, f"{pkg}.json"), "w", newline="") as f:
                        json.dump(profile, f, indent=2)
                    _debug(f"  Saved profile: permissions/{pkg}.json")

                    svc_path = os.path.join(extract_dir, "service.sh")
                    if not os.path.exists(svc_path):
                        svc_content = (
                            "#!/system/bin/sh\n"
                            "LOGFILE=\"$(dirname \"$0\")/service.log\"\n"
                            "log() { echo \"[$(date '+%Y-%m-%d %H:%M:%S')] $1\" | tee -a \"$LOGFILE\"; }\n"
                            "log \"=== service.sh start ===\"\n"
                            "MODDIR=${0%/*}\n"
                            "PERM_DIR=\"$MODDIR/permissions\"\n"
                            "log \"MODDIR=$MODDIR\"\n"
                            "log \"PERM_DIR=$PERM_DIR\"\n"
                            "\n"
                            "while [ \"$(getprop sys.boot_completed)\" != \"1\" ]; do sleep 1; done\n"
                            "sleep 3\n"
                            "log \"Boot completed, processing profiles...\"\n"
                            "\n"
                            "COUNT=0\n"
                            "GRANTED=0\n"
                            "ENABLED=0\n"
                            "for profile in \"$PERM_DIR\"/*.json; do\n"
                            "    [ -f \"$profile\" ] || continue\n"
                            "    PKG=$(basename \"$profile\" .json)\n"
                            "    COUNT=$((COUNT + 1))\n"
                            "    log \"--- Processing: $PKG ---\"\n"
                            "\n"
                            "    if ! pm list packages 2>/dev/null | grep -q \"package:$PKG\"; then\n"
                            "        log \"SKIP: $PKG not installed\"\n"
                            "        continue\n"
                            "    fi\n"
                            "    log \"FOUND: $PKG is installed\"\n"
                            "\n"
                            "    log \"Granting runtime permissions...\"\n"
                            "    grep -o '\"android\\.[^\"]*\"' \"$profile\" | tr -d '\"' | while read perm; do\n"
                            "        if pm grant \"$PKG\" \"$perm\" 2>/dev/null; then\n"
                            "            log \"  GRANTED: $perm\"\n"
                            "        else\n"
                            "            log \"  SKIP: $perm (already granted or not applicable)\"\n"
                            "        fi\n"
                            "        GRANTED=$((GRANTED + 1))\n"
                            "    done\n"
                            "\n"
                            "    if grep -q '\"hide_disable\": *true' \"$profile\"; then\n"
                            "        if pm enable \"$PKG\" 2>/dev/null; then\n"
                            "            log \"ENABLED: $PKG\"\n"
                            "            ENABLED=$((ENABLED + 1))\n"
                            "        else\n"
                            "            log \"ENABLE SKIP: $PKG (already enabled)\"\n"
                            "        fi\n"
                            "    fi\n"
                            "\n"
                            "    if magisk resetprop -n \"persist.sys.priapp.$PKG\" \"1\" 2>/dev/null; then\n"
                            "        log \"RESETPROP: persist.sys.priapp.$PKG=1\"\n"
                            "    else\n"
                            "        log \"RESETPROP SKIP: $PKG (magisk not available)\"\n"
                            "    fi\n"
                            "\n"
                            "    log \"--- Done: $PKG ---\"\n"
                            "done\n"
                            "\n"
                            "log \"Summary: profiles=$COUNT granted=$GRANTED enabled=$ENABLED\"\n"
                            "log \"=== service.sh end ===\"\n"
                        )
                        with open(svc_path, "w", newline="") as f:
                            f.write(svc_content)
                        _debug(f"  Injected service.sh to EROFS")

                    # one merged XML per type: re-derive every package from
                    # permissions/*.json so app A's block survives app B
                    priv_pkgs, def_pkgs = InitrdManager.regenerate_permission_xmls(
                        extract_dir)
                    log(f"Permission XML: {LSP_PRIV_XML} "
                        f"({len(priv_pkgs)} packages), "
                        f"{LSP_DEF_XML} ({len(def_pkgs)} packages)")

                    _debug("  Repacking EROFS image")
                    initrd.repack_lsp_image()
                    log(f"Added {pkg}")
                else:
                    log("Failed to extract image, creating new")
                    _debug("  Creating new LSP image from scratch")
                    image_data = initrd.create_lsp_image([apk_path], {pkg: profile})
                    arcname = f"overlay.d/sbin/{LSP_IMAGE_NAME}"
                    if CpioUtils.has_file(initrd.path, arcname):
                        CpioUtils.delete_file(initrd.path, arcname)
                    CpioUtils.add_file(initrd.path, arcname, image_data)
                    _debug(f"  add_file({arcname}, {len(image_data):,} bytes)")
                    log(f"Added {pkg}")
            else:
                _debug("No lsp image, creating new")
                image_data = initrd.create_lsp_image([apk_path], {pkg: profile})
                arcname = f"overlay.d/sbin/{LSP_IMAGE_NAME}"
                CpioUtils.add_file(initrd.path, arcname, image_data)
                _debug(f"  add_file({arcname}, {len(image_data):,} bytes)")
                log(f"Added {pkg}")
            time.sleep(0.5)

        if is_wsa_img:
            log("Starting WSA...")
            WSADetector.ensure_running()
            time.sleep(15)

        log("Installation complete!")
        print("\n  System app installation complete. Tool will close now.", flush=True)
        time.sleep(2)
        window.request_close()

    def status(self, initrd_path=None):
        print(f"{APP_NAME} v{APP_VERSION}")
        print("=" * 50)

        if initrd_path:
            _debug(f"status() with path: {initrd_path}")
            if not os.path.exists(initrd_path):
                print(f"File not found: {initrd_path}")
                return
            fsize = os.path.getsize(initrd_path)
            print(f"File: {initrd_path}")
            print(f"Size: {fsize:,} bytes")
            initrd = InitrdManager(initrd_path)
            if initrd.is_stock():
                print("Recovery system: STOCK (no TWRP)")
                return
            info = initrd.read_info()
            if info:
                print(f"TWRP Support: {info.get('twrp_support', False)}")
                missing = initrd.twrp_missing()
                print(f"Missing TWRP files: {', '.join(missing) if missing else 'none'}")
                print(f"GApps Support: {info.get('gapp_support', False)}")
                print(f"Root Support: {info.get('root_support', False)}")
                print(f"Root Method: {info.get('root_method', 'Unknown')}")
                print(f"Amazon Support: {info.get('amazon_support', 'Unknown')}")
                print(f"Recovery Flag: {initrd.get_recovery_flag()}")
                print(f"Build Version: {info.get('build_version', 'Unknown')}")
                print(f"WSA Version: {info.get('wsa_version', 'Unknown')}")
                note = info.get('note', '')
                if note:
                    print(f"Note: {note}")
            else:
                print("Recovery system: PRESENT (no info.json)")
            return

        _debug("status() with WSA detection")
        wsa_path = WSADetector.find_path()
        if not wsa_path:
            print("WSA: NOT INSTALLED")
            return
        print(f"WSA Path: {wsa_path}")
        print(f"WSA Running: {WSADetector.is_running()}")
        initrd_path = WSADetector.initrd_path(wsa_path)
        if not os.path.exists(initrd_path):
            print("Recovery system: NOT FOUND")
            return
        initrd = InitrdManager(initrd_path)
        if initrd.is_stock():
            print("Recovery system: STOCK (no TWRP)")
            return
        info = initrd.read_info()
        if info:
            print(f"TWRP Support: {info.get('twrp_support', False)}")
            missing = initrd.twrp_missing()
            print(f"Missing TWRP files: {', '.join(missing) if missing else 'none'}")
            print(f"GApps Support: {info.get('gapp_support', False)}")
            print(f"Root Support: {info.get('root_support', False)}")
            print(f"Root Method: {info.get('root_method', 'Unknown')}")
            print(f"Amazon Support: {info.get('amazon_support', 'Unknown')}")
            print(f"Recovery Flag: {initrd.get_recovery_flag()}")
            print(f"Build Version: {info.get('build_version', 'Unknown')}")
            print(f"WSA Version: {info.get('wsa_version', 'Unknown')}")
            note = info.get('note', '')
            if note:
                print(f"Note: {note}")
        else:
            print("Recovery system: PRESENT (no info.json)")

        for m in ("admin", "user"):
            select_image(m)
            self._status_lsp_apps(initrd)

    def _status_lsp_apps(self, initrd):
        if initrd.has_lsp_image():
            print()
            print(f"System Apps ({LSP_IMAGE_NAME}) [{LSP_LABEL}]")
            print("-" * 50)
            extract_dir = initrd.extract_lsp_image()
            if extract_dir:
                perm_dir = os.path.join(extract_dir, "permissions")
                priv_app = os.path.join(extract_dir, "system", "priv-app")
                apk_pkgs = []
                if os.path.isdir(priv_app):
                    for pkg_dir in sorted(os.listdir(priv_app)):
                        pkg_path = os.path.join(priv_app, pkg_dir)
                        if os.path.isdir(pkg_path):
                            apk_files = [f for f in os.listdir(pkg_path) if f.endswith(".apk")]
                            if apk_files:
                                apk_pkgs.append(pkg_dir)
                profiles = {}
                if os.path.isdir(perm_dir):
                    for jf in os.listdir(perm_dir):
                        if jf.endswith(".json"):
                            pkg_name = jf[:-5]
                            try:
                                with open(os.path.join(perm_dir, jf)) as f:
                                    profiles[pkg_name] = json.load(f)
                            except Exception:
                                pass
                if not apk_pkgs:
                    print("  (no system apps installed)")
                else:
                    for pkg in apk_pkgs:
                        profile = profiles.get(pkg, {})
                        hide_u = profile.get("hide_uninstall", True)
                        hide_d = profile.get("hide_disable", True)
                        privapp = profile.get("privapp_perms", [])
                        runtime = profile.get("runtime_perms", [])
                        print(f"  {pkg}")
                        print(f"    Uninstall: {'hidden' if hide_u else 'visible'}")
                        print(f"    Disable: {'hidden' if hide_d else 'visible'}")
                        print(f"    Privileged: {len(privapp)} permissions")
                        if privapp:
                            for p in privapp:
                                print(f"      - {p}")
                        print(f"    Runtime: {len(runtime)} permissions")
                        if runtime:
                            for p in runtime:
                                print(f"      - {p}")
                        print()
                shutil.rmtree(LSP_TEMP, ignore_errors=True)
            else:
                print("  Failed to extract image")
        else:
            print()
            print(f"System Apps ({LSP_IMAGE_NAME}) [{LSP_LABEL}]: NOT PRESENT")

    def list_boltware(self, initrd_path=None, mode=None):
        if initrd_path:
            if not os.path.exists(initrd_path):
                print(f"File not found: {initrd_path}")
                return
            initrd = InitrdManager(initrd_path)
        else:
            wsa_path = WSADetector.find_path()
            if not wsa_path:
                print("WSA not found!")
                return
            initrd_path = WSADetector.initrd_path(wsa_path)
            if not os.path.exists(initrd_path):
                print("Recovery system not found!")
                return
            initrd = InitrdManager(initrd_path)

        if initrd.is_stock():
            print("Recovery system: STOCK (no TWRP)")
            return

        print(f"{APP_NAME} v{APP_VERSION}")
        print("=" * 50)

        for m in (["admin", "user"] if mode is None else [mode]):
            select_image(m)
            self._list_lsp_apps(initrd)

    def _list_lsp_apps(self, initrd):
        if not initrd.has_lsp_image():
            print(f"\nSystem Apps ({LSP_IMAGE_NAME}) [{LSP_LABEL}]: NOT PRESENT")
            return

        extract_dir = initrd.extract_lsp_image()
        if not extract_dir:
            print("Failed to extract image")
            return

        try:
            perm_dir = os.path.join(extract_dir, "permissions")
            priv_app = os.path.join(extract_dir, "system", "priv-app")

            profiles = {}
            if os.path.isdir(perm_dir):
                for jf in os.listdir(perm_dir):
                    if jf.endswith(".json"):
                        pkg_name = jf[:-5]
                        try:
                            with open(os.path.join(perm_dir, jf)) as f:
                                profiles[pkg_name] = json.load(f)
                        except Exception:
                            pass

            apk_pkgs = []
            if os.path.isdir(priv_app):
                for pkg_dir in sorted(os.listdir(priv_app)):
                    pkg_path = os.path.join(priv_app, pkg_dir)
                    if os.path.isdir(pkg_path):
                        apk_files = [f for f in os.listdir(pkg_path) if f.endswith(".apk")]
                        if apk_files:
                            apk_pkgs.append((pkg_dir, apk_files))

            print(f"\nSystem Apps ({LSP_IMAGE_NAME}) [{LSP_LABEL}]")
            print("-" * 50)

            if not apk_pkgs:
                print("  (no system apps installed)")
            else:
                for pkg, apk_files in apk_pkgs:
                    profile = profiles.get(pkg, {})
                    privapp = profile.get("privapp_perms", [])
                    runtime = profile.get("runtime_perms", [])
                    print(f"\n  {pkg}")
                    for apk in apk_files:
                        apk_path = os.path.join(priv_app, pkg, apk)
                        apk_size = os.path.getsize(apk_path)
                        print(f"    APK: {apk} ({apk_size:,} bytes)")
                    print(f"    Privileged: {len(privapp)} permissions")
                    print(f"    Runtime: {len(runtime)} permissions")

            print(f"\nTotal: {len(apk_pkgs)} app(s)")
        finally:
            shutil.rmtree(LSP_TEMP, ignore_errors=True)

    def uninstall_boltware(self, apk_name=None, initrd_path=None, mode=None):
        if initrd_path:
            if not os.path.exists(initrd_path):
                print(f"File not found: {initrd_path}")
                return
            initrd = InitrdManager(initrd_path)
        else:
            wsa_path = WSADetector.find_path()
            if not wsa_path:
                print("WSA not found!")
                return
            initrd_path = WSADetector.initrd_path(wsa_path)
            if not os.path.exists(initrd_path):
                print("Recovery system not found!")
                return
            initrd = InitrdManager(initrd_path)

        if initrd.is_stock():
            print("Recovery system: STOCK (no TWRP)")
            return

        modes = ["admin", "user"] if mode is None else [mode]
        pending = []
        for m in modes:
            select_image(m)
            pending.extend(self._uninstall_boltware_image(initrd, apk_name))
        pending = list(dict.fromkeys(pending))
        if pending:
            initrd.patch_postfsdata_uninstall()
            initrd.inject_uninstall_txt(pending)
            print(f"Uninstall scheduled for {len(pending)} package(s) on next boot")
            print("IMPORTANT: uninstall.txt lives inside the image and the list "
                  "runs on EVERY boot.")
            print("After the next boot has removed the app, run "
                  "--cleanup-uninstall ('Uninstall temp cleanup' in the manager)")
            print("to clear it - otherwise a later reinstall would be removed "
                  "again on the next boot.")

    def _uninstall_boltware_image(self, initrd, apk_name):
        arcname = f"overlay.d/sbin/{LSP_IMAGE_NAME}"
        schedule = []

        if apk_name is None:
            if not CpioUtils.has_file(initrd.path, arcname):
                print(f"[{LSP_LABEL}] {LSP_IMAGE_NAME} not present, nothing to remove")
                return schedule
            extract_dir = initrd.extract_lsp_image()
            all_packages = []
            if extract_dir:
                priv_app = os.path.join(extract_dir, "system", "priv-app")
                if os.path.isdir(priv_app):
                    for d in os.listdir(priv_app):
                        if os.path.isdir(os.path.join(priv_app, d)):
                            all_packages.append(d)
                shutil.rmtree(extract_dir, ignore_errors=True)
            CpioUtils.delete_file(initrd.path, arcname)
            print(f"Removed {LSP_IMAGE_NAME} entirely")
            return all_packages

        if not initrd.has_lsp_image():
            print(f"[{LSP_LABEL}] {LSP_IMAGE_NAME} not present")
            return [apk_name]

        extract_dir = initrd.extract_lsp_image()
        if not extract_dir:
            print("Failed to extract image")
            return schedule

        try:
            pkg_dir = os.path.join(extract_dir, "system", "priv-app", apk_name)
            perm_file = os.path.join(extract_dir, "permissions", f"{apk_name}.json")

            removed_something = False

            if os.path.isdir(pkg_dir):
                shutil.rmtree(pkg_dir)
                print(f"Removed system/priv-app/{apk_name}/")
                removed_something = True

            if os.path.isfile(perm_file):
                os.remove(perm_file)
                print(f"Removed permissions/{apk_name}.json")
                removed_something = True

            if not removed_something:
                print(f"{apk_name} not found in image")
            else:
                priv_app = os.path.join(extract_dir, "system", "priv-app")
                remaining = []
                if os.path.isdir(priv_app):
                    for d in os.listdir(priv_app):
                        if os.path.isdir(os.path.join(priv_app, d)):
                            remaining.append(d)

                if not remaining:
                    CpioUtils.delete_file(initrd.path, arcname)
                    print(f"Image empty, removed {LSP_IMAGE_NAME} entirely")
                else:
                    InitrdManager.regenerate_permission_xmls(
                        extract_dir, removed_pkgs=[apk_name])
                    initrd.repack_lsp_image()
                    print(f"Removed {apk_name} from {LSP_IMAGE_NAME}")

            return [apk_name]
        finally:
            shutil.rmtree(LSP_TEMP, ignore_errors=True)

    def install_magisk_hook(self, initrd_path=None):
        return self._launch_gui(self._flow_install_magisk_hook, dict(
            target_initrd=initrd_path,
        ))

    def repair_magisk_hook(self, initrd_path=None):
        return self._launch_gui(self._flow_install_magisk_hook, dict(
            target_initrd=initrd_path,
            force=True,
        ))

    def uninstall_magisk_hook(self, initrd_path=None):
        return self._launch_gui(self._flow_uninstall_magisk_hook, dict(
            target_initrd=initrd_path,
        ))

    def cleanup_uninstall(self, initrd_path=None):
        return self._launch_gui(self._flow_cleanup_uninstall, dict(
            target_initrd=initrd_path,
        ))

    @staticmethod
    def _choose_backup_file(path):
        """Pick one <file>.img.bak-* next to `path`; None when cancelled."""
        folder = os.path.dirname(path) or "."
        prefix = os.path.basename(path) + ".bak-"
        try:
            found = sorted(name for name in os.listdir(folder)
                           if name.startswith(prefix))
        except OSError:
            return None
        if not found:
            return None
        picked, ok = QInputDialog.getItem(
            None, APP_NAME, "Backup:", found, 0, False)
        if not ok or not picked:
            return None
        return os.path.join(folder, picked)

    def manage_img(self, initrd_path=None):
        """Open the IMG Manager window.

        Sole caller is the --gui branch of main(); no other flow reaches it.
        """
        _debug(f"manage_img({initrd_path})")
        # QApplication must exist before ANY QMessageBox/QFileDialog call
        # (right-click "Open with" can reach those before the window opens).
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setStyle("Fusion")
        path = initrd_path
        if path:
            if not os.path.isfile(path):
                QMessageBox.critical(None, APP_NAME, f"File not found:\n{path}")
                return 1
        else:
            wsa = WSADetector.find_path()
            if wsa:
                candidate = os.path.join(wsa, "Tools", "initrd.img")
                if os.path.isfile(candidate):
                    path = candidate
                else:
                    _debug(f"manage_img: not present: {candidate}")
            else:
                _debug("manage_img: WSADetector.find_path() -> None")
            if not path:
                path, _filter = QFileDialog.getOpenFileName(
                    None, "Select initrd.img", "",
                    "Images (*.img);;All files (*.*)")
                if not path:
                    print("  No image selected.", flush=True)
                    return 1

        source = None
        failure = None
        try:
            entries = CpioUtils.list_entries(path)
            if not entries:
                failure = "Empty cpio image."
        except Exception as exc:
            entries = []
            failure = f"Not a readable cpio image: {exc}"

        if failure:
            answer = QMessageBox.question(
                None, APP_NAME,
                f"{failure}\n{path}\n\n"
                "The live image cannot be opened.\n"
                "Load one of its backups instead?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                QMessageBox.critical(None, APP_NAME, f"{failure}:\n{path}")
                return 1
            source = self._choose_backup_file(path)
            if not source:
                return 1
            try:
                entries = CpioUtils.list_entries(source)
            except Exception as exc:
                QMessageBox.critical(
                    None, APP_NAME,
                    f"Backup is unreadable:\n{source}\n\n{exc}")
                return 1
            if not entries:
                QMessageBox.critical(None, APP_NAME, f"Backup is empty:\n{source}")
                return 1

        if source:
            _log(f"Opening IMG Manager from backup: {source} -> {path}")
        else:
            _log(f"Opening IMG Manager: {path} ({len(entries)} entries)")
        window = ImgManagerWindow(path, source_path=source)
        screen = app.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            window.move(
                available.center().x() - window.width() // 2,
                available.center().y() - window.height() // 2,
            )
        window.show()
        result = app.exec()
        self._cleanup()
        return result

    def _flow_install_magisk_hook(self, log, window, target_initrd=None, force=False):
        is_wsa_img = False
        if target_initrd:
            initrd_path = target_initrd
            if not os.path.exists(initrd_path):
                log(f"File not found: {initrd_path}")
                time.sleep(2)
                window.request_close()
                return
            log(f"File: {os.path.basename(initrd_path)} ({os.path.getsize(initrd_path):,} bytes)")
            wsa_path = WSADetector.find_path()
            if wsa_path:
                if os.path.normpath(initrd_path) == os.path.normpath(WSADetector.initrd_path(wsa_path)):
                    is_wsa_img = True
                    log("Detected: WSA recovery system")
                else:
                    log("Detected: external file (not WSA)")
            else:
                log("Detected: standalone file (no WSA)")
        else:
            log("Checking WSA installation...")
            time.sleep(1)
            wsa_path = WSADetector.find_path()
            if not wsa_path:
                log("WSA not found!")
                time.sleep(2)
                window.request_close()
                return
            log(f"WSA found: {os.path.basename(wsa_path)}")
            initrd_path = WSADetector.initrd_path(wsa_path)
            if not os.path.exists(initrd_path):
                log("Recovery system not found!")
                time.sleep(2)
                window.request_close()
                return
            is_wsa_img = True
        time.sleep(0.5)

        initrd = InitrdManager(initrd_path)

        existing = {name for name, *_ in CpioUtils.scan_entries(initrd.path)}
        hook_present = POSTFSDATA_ARCNAME in existing
        if hook_present and not force:
            issues = initrd.hook_issues()
            if not issues:
                log("Magisk hook already installed, nothing to do")
                log("")
                log("To install apps as system app:")
                log(f"  {CLI_NAME} --install-as-system-app <path_of_apk>")
                log(f"  {CLI_NAME} --install-as-system-app <path_of_apk> --admin")
                time.sleep(2)
                window.request_close()
                return

            log("Magisk hook found with problems:")
            for issue in issues:
                log(f"  - {issue}")
            if is_wsa_img:
                log("Stopping WSA...")
                KillWSA.kill_all()
                time.sleep(3)
            else:
                log("Patching file directly...")
            initrd.repair_hook_infrastructure()
            log("Magisk hook repaired")

            if is_wsa_img:
                log("Starting WSA...")
                WSADetector.ensure_running()
                time.sleep(15)
            time.sleep(2)
            window.request_close()
            return

        if is_wsa_img:
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        else:
            log("Patching file directly...")

        if force and hook_present:
            log("Overriding existing Magisk hook (full rebuild from fix.7z)...")
            hook_ok = initrd.override_hook_infrastructure()
        else:
            log("Installing Magisk hook...")
            hook_ok = initrd.add_hook_infrastructure()
        if hook_ok:
            log("Magisk hook installed successfully!")
            log("")
            log("To install apps as system app:")
            log(f"  {CLI_NAME} --install-as-system-app <path_of_apk>")
            log("")
            log("To list installed system apps:")
            log(f"  {CLI_NAME} --list-of-boltware")
            log("")
            log("To uninstall a system app:")
            log(f"  {CLI_NAME} --uninstall-boltware <package_name>")
        else:
            log("Failed to install Magisk hook!")

        if is_wsa_img:
            log("Starting WSA...")
            WSADetector.ensure_running()
            time.sleep(15)

        time.sleep(2)
        window.request_close()

    def _flow_uninstall_magisk_hook(self, log, window, target_initrd=None):
        _debug("_flow_uninstall_magisk_hook() started")
        resolved = self._resolve_initrd(log, window, target_initrd)
        if resolved is None:
            return
        initrd_path, is_wsa_img = resolved

        initrd = InitrdManager(initrd_path)
        present = {name for name, *_ in CpioUtils.scan_entries(initrd_path)}
        hook_present = (POSTFSDATA_ARCNAME in present
                        or "lspinit" in present
                        or "overlay.d/init.lsp.magisk.rc" in present)
        if not hook_present:
            log("Magisk hook is not installed - nothing to remove")
            time.sleep(2)
            window.request_close()
            return

        if is_wsa_img:
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        else:
            log("Patching file directly...")

        log("Removing Magisk hook...")

        # 1. /init: the hook replaced it with a symlink to lspinit and put the
        #    WSA init aside as wsainit - swap them back
        init_mode = next(
            (m for n, m, _s in CpioUtils.list_entries(initrd_path)
             if n == "init"), None)
        init_is_link = init_mode is not None and (init_mode & 0o170000) == 0o120000
        if "wsainit" in present:
            if init_mode is not None:
                CpioUtils.delete_file(initrd_path, "init")
                log("  removed /init" + (" (symlink)" if init_is_link else ""))
            CpioUtils.rename_entry(initrd_path, "wsainit", "init")
            log("  wsainit -> init")
        elif init_is_link:
            log("WARNING: wsainit missing and /init is a symlink -")
            log("  cannot restore a bootable init, aborting (nothing removed)")
            time.sleep(3)
            window.request_close()
            return
        elif init_mode is not None:
            log("  kept /init (real file present, wsainit missing)")
        else:
            log("  WARNING: no /init and no wsainit - nothing to restore")

        # 2. the hook payload itself
        hook_files = (
            "lspinit",
            "magiskinit",
            "overlay.d/init.lsp.magisk.rc",
            POSTFSDATA_ARCNAME,
            "overlay.d/sbin/init-ld.xz",
            "overlay.d/sbin/magisk.xz",
            "overlay.d/sbin/stub.xz",
            "overlay.d/sbin/uninstall.txt",
        )
        removed = 0
        for name in hook_files:
            if name in present:
                CpioUtils.delete_file(initrd_path, name)
                log(f"  removed /{name}")
                removed += 1
        if ".backup" in present:
            CpioUtils.delete_tree(initrd_path, ".backup")
            log("  removed /.backup/")
            removed += 1

        # 3. whatever is left under overlay.d/ (module images included) goes
        #    with the hook - the directory only exists for it
        remaining = {name for name, *_ in CpioUtils.scan_entries(initrd_path)}
        leftovers = sorted(n for n in remaining
                           if n == "overlay.d" or n.startswith("overlay.d/"))
        for name in leftovers:
            log(f"  removed /{name}")
            removed += 1
        if leftovers:
            CpioUtils.delete_tree(initrd_path, "overlay.d")
            log("  /overlay.d/ tree removed")

        log(f"Magisk hook uninstalled ({removed} entries removed)")

        if is_wsa_img:
            log("Starting WSA...")
            WSADetector.ensure_running()
            time.sleep(15)
        else:
            log("Patch complete!")
        time.sleep(1)
        window.request_close()

    def _flow_cleanup_uninstall(self, log, window, target_initrd=None):
        """Delete overlay.d/sbin/uninstall.txt - the pending uninstall list.

        The boot handler consumes its runtime copy but the archive entry in
        initrd.img survives every reboot, so the same list would keep running
        on each boot (and remove the app again after a later reinstall).
        """
        _debug("_flow_cleanup_uninstall() started")
        resolved = self._resolve_initrd(log, window, target_initrd)
        if resolved is None:
            return
        initrd_path, is_wsa_img = resolved

        arcname = "overlay.d/sbin/uninstall.txt"
        if not CpioUtils.has_file(initrd_path, arcname):
            log("No uninstall.txt - nothing to clean")
            time.sleep(2)
            window.request_close()
            return

        try:
            data = CpioUtils.read_file(initrd_path, arcname)
        except Exception:
            data = b""
        packages = [line.strip() for line
                    in data.decode("utf-8", "replace").splitlines()
                    if line.strip()]
        if packages:
            log(f"Scheduled list: {', '.join(packages)}")
        log(f"Removing /{arcname}...")
        CpioUtils.delete_file(initrd_path, arcname)
        log(f"Removed uninstall.txt ({len(packages)} package(s) cleared)")
        log("The boot handler will no longer re-run these uninstalls")
        time.sleep(1)
        window.request_close()


def _parse_into(args_list):
    if args_list is None:
        return None, "/"
    if "into" in args_list:
        idx = args_list.index("into")
        path = args_list[0] if idx > 0 else None
        dest = "/".join(args_list[idx + 1:]) if idx + 1 < len(args_list) else "/"
        return path, dest
    return args_list[0] if args_list else None, "/"


def main():
    global DEBUG, LOG_FOR_USER
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {CLI_NAME}                                              Auto-inject + boot TWRP
  {CLI_NAME} --path C:\\initrd.img                         Patch specific file
  {CLI_NAME} --status                                     Check WSA status
  {CLI_NAME} --status --path C:\\initrd.img               Check specific file
  {CLI_NAME} --enable-twrp                                Set recovery flag
  {CLI_NAME} --enable-twrp --path C:\\initrd.img          Set flag in file
  {CLI_NAME} --disable-twrp                               Clear recovery flag
  {CLI_NAME} --disable-twrp --path C:\\initrd.img         Clear flag in file
  {CLI_NAME} --inject-file info.json                      Inject file
  {CLI_NAME} --inject-file info.json into /info/          Inject into subfolder
  {CLI_NAME} --inject-folder assest/twrp/                 Inject folder
  {CLI_NAME} --inject assets/test.7z                      Extract 7z + patch.json
  {CLI_NAME} --install-as-system-app app.apk              Install APK as system app
  {CLI_NAME} --install-as-system-app a.apk b.apk          Install multiple APKs
  {CLI_NAME} --list-of-boltware                           List system apps
  {CLI_NAME} --uninstall-boltware com.wsa.webdav          Remove specific app
  {CLI_NAME} --uninstall-boltware                          Remove all system apps
  {CLI_NAME} --cleanup-uninstall                           Clear uninstall.txt after the removal boot
  {CLI_NAME} --install-as-system-app app.apk              Install into USER module (default)
  {CLI_NAME} --install-as-system-app app.apk --admin      Install into ADMIN module (password)
  {CLI_NAME} --update-as-system-app app.apk --admin       Update inside ADMIN module (password)
  {CLI_NAME} --list-of-boltware --user                    List apps in USER module only
  {CLI_NAME} --install-magisk-hook                         Install Magisk hook only
  {CLI_NAME} --repaire-magisk-hook                         Force rebuild Magisk hook (overrides existing)
  {CLI_NAME} --uninstall-magisk-hook                       Remove Magisk hook (wsainit becomes /init)
  {CLI_NAME} --install-twrp                                Install TWRP + set twrp_support=true
  {CLI_NAME} --repair-twrp                                 Force re-inject TWRP payload + fix flags
  {CLI_NAME} --uninstall-twrp                              Remove TWRP files + clear both flags
  {CLI_NAME} --gui                                         Open the initrd.img file manager GUI
  {CLI_NAME} --gui --path C:\\initrd.img                   Manage a specific file
  {CLI_NAME} --register-img                                Add .img -> Open with -> WSA IMG Manager
  {CLI_NAME} --unregister-img                              Remove the .img Open with entries
        """)
    parser.add_argument("--status", action="store_true",
                        help="Check WSA and TWRP status")
    parser.add_argument("--gui", action="store_true",
                        help="Open the initrd.img file manager GUI (extract/delete/rename/overwrite)")
    parser.add_argument("--disable-twrp", action="store_true",
                        help="Clear recovery flag (force normal boot)")
    parser.add_argument("--enable-twrp", action="store_true",
                        help="Set recovery flag to true (boot TWRP)")
    parser.add_argument("--path", type=str, default=None,
                        help="Path to initrd.img to patch directly")
    parser.add_argument("--inject-file", nargs='*', default=None,
                        help="Inject single file: --inject-file FILE [into DEST]")
    parser.add_argument("--inject-folder", nargs='*', default=None,
                        help="Inject folder contents: --inject-folder FOLDER [into DEST]")
    parser.add_argument("--inject", nargs='*', default=None,
                        help="Extract 7z + patch.json: --inject SEVENZ [into DEST]")
    parser.add_argument("--install-as-system-app", nargs='+', default=None,
                        help="Install APK(s) as system app: --install-as-system-app APK1 [APK2 ...]")
    parser.add_argument("--update-as-system-app", nargs='+', default=None,
                        help="Update/reinstall APK(s) as system app (overrides existing)")
    parser.add_argument("--list-of-boltware", action="store_true",
                        help="List all system apps in both module images")
    parser.add_argument("--uninstall-boltware", nargs='?', const="", default=None,
                        help="Remove app from the module images (no arg = remove entire image)")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--admin", action="store_true",
                            help="Target the ADMIN module image lsp_wsa-installer.img "
                                 "(id wsa-installer). Password protected.")
    mode_group.add_argument("--user", action="store_true",
                            help="Target the USER module image lsp_wsa-installer-user.img "
                                 "(id wsa-installer-user). Default for install/update.")
    parser.add_argument("--install-magisk-hook", action="store_true",
                        help="Install Magisk hook infrastructure only")
    parser.add_argument("--repaire-magisk-hook", "--repair-magisk-hook",
                        action="store_true", dest="repair_magisk_hook",
                        help="Force rebuild of the Magisk hook, overriding an existing one")
    parser.add_argument("--uninstall-magisk-hook", action="store_true",
                        help="Remove the Magisk hook (wsainit is renamed back to /init)")
    parser.add_argument("--cleanup-uninstall", action="store_true",
                        help="Delete overlay.d/sbin/uninstall.txt (pending uninstall list); "
                             "run once after the boot that applied an uninstall")
    parser.add_argument("--install-twrp", action="store_true",
                        help="Install TWRP recovery files and set twrp_support=true")
    parser.add_argument("--repair-twrp", action="store_true",
                        help="Force re-inject the TWRP payload and fix twrp_support")
    parser.add_argument("--uninstall-twrp", action="store_true",
                        help="Remove TWRP files and folders, set twrp_support=false "
                             "and recovery_flag=false")
    parser.add_argument("--register-img", action="store_true",
                        help="Register .img files -> Open with -> WSA IMG Manager (Explorer)")
    parser.add_argument("--unregister-img", action="store_true",
                        help="Remove the .img Open with / context-menu registration")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug output")
    args = parser.parse_args()

    if args.debug:
        DEBUG = True
        LOG_FOR_USER = True
        _debug("Debug mode enabled")

    _debug(f"args: status={args.status}, path={args.path}, enable={args.enable_twrp}, "
           f"disable={args.disable_twrp}, inject_file={args.inject_file}, "
           f"inject_folder={args.inject_folder}, inject={args.inject}, "
           f"install_as_system_app={args.install_as_system_app}")
    mode = "admin" if args.admin else ("user" if args.user else None)
    _debug(f"mode: {mode or 'default'}")

    if args.register_img:
        _debug("Command: --register-img")
        sys.exit(register_img_handler())

    if args.unregister_img:
        _debug("Command: --unregister-img")
        sys.exit(unregister_img_handler())

    if args.gui:
        _debug("Command: --gui")
        twrp = WSATWRP()
        sys.exit(twrp.manage_img(initrd_path=args.path))

    if args.status:
        _debug("Command: --status")
        twrp = WSATWRP()
        twrp.status(initrd_path=args.path)
        return

    if args.disable_twrp:
        _debug("Command: --disable-twrp")
        twrp = WSATWRP()
        twrp.disable_twrp(initrd_path=args.path)
        return

    if args.enable_twrp:
        _debug("Command: --enable-twrp")
        twrp = WSATWRP()
        twrp.enable_twrp(initrd_path=args.path)
        return

    if args.install_as_system_app is not None:
        _debug("Command: --install-as-system-app")
        twrp = WSATWRP()
        twrp.install_as_system_app(
            apk_paths=args.install_as_system_app,
            target_initrd=args.path,
            mode=mode,
        )
        return

    if args.update_as_system_app is not None:
        _debug("Command: --update-as-system-app")
        twrp = WSATWRP()
        twrp.install_as_system_app(
            apk_paths=args.update_as_system_app,
            target_initrd=args.path,
            force_update=True,
            mode=mode,
        )
        return

    if args.list_of_boltware:
        _debug("Command: --list-of-boltware")
        twrp = WSATWRP()
        twrp.list_boltware(initrd_path=args.path, mode=mode)
        return

    if args.uninstall_boltware is not None:
        _debug("Command: --uninstall-boltware")
        twrp = WSATWRP()
        twrp.uninstall_boltware(
            apk_name=args.uninstall_boltware or None,
            initrd_path=args.path,
            mode=mode,
        )
        return

    if args.cleanup_uninstall:
        _debug("Command: --cleanup-uninstall")
        twrp = WSATWRP()
        twrp.cleanup_uninstall(initrd_path=args.path)
        return

    if args.repair_magisk_hook:
        _debug("Command: --repaire-magisk-hook")
        twrp = WSATWRP()
        twrp.repair_magisk_hook(initrd_path=args.path)
        return

    if args.install_magisk_hook:
        _debug("Command: --install-magisk-hook")
        twrp = WSATWRP()
        twrp.install_magisk_hook(initrd_path=args.path)
        return

    if args.uninstall_magisk_hook:
        _debug("Command: --uninstall-magisk-hook")
        twrp = WSATWRP()
        twrp.uninstall_magisk_hook(initrd_path=args.path)
        return

    if args.uninstall_twrp:
        _debug("Command: --uninstall-twrp")
        twrp = WSATWRP()
        twrp.uninstall_twrp(initrd_path=args.path)
        return

    if args.repair_twrp:
        _debug("Command: --repair-twrp")
        twrp = WSATWRP()
        twrp.repair_twrp(initrd_path=args.path)
        return

    if args.install_twrp:
        _debug("Command: --install-twrp")
        twrp = WSATWRP()
        twrp.install_twrp(initrd_path=args.path)
        return

    inject_file, inject_folder, inject_7z = None, None, None
    inject_dest = "/"

    if args.inject_file is not None:
        inject_file, inject_dest = _parse_into(args.inject_file)
        _debug(f"inject_file: {inject_file} -> {inject_dest}")
    elif args.inject_folder is not None:
        inject_folder, inject_dest = _parse_into(args.inject_folder)
        _debug(f"inject_folder: {inject_folder} -> {inject_dest}")
    elif args.inject is not None:
        inject_7z, inject_dest = _parse_into(args.inject)
        _debug(f"inject_7z: {inject_7z} -> {inject_dest}")

    _debug("Command: boot_to_twrp")
    twrp = WSATWRP()
    twrp.boot_to_twrp(
        target_initrd=args.path,
        inject_file=inject_file,
        inject_folder=inject_folder,
        inject_7z=inject_7z,
        inject_dest=inject_dest,
    )


if __name__ == "__main__":
    main()
