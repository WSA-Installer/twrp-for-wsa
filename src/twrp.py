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
import subprocess
import time
import shutil
import socket
import ctypes
import argparse
import struct
import threading
import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget,
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
INJECT_TEMP = os.path.join(os.environ.get("TEMP", os.environ.get("TMP", tempfile.gettempdir())), "twrp_temp")
LSP_TEMP = os.path.join(INJECT_TEMP, "lsp_installer")
FIX_TEMP = os.path.join(INJECT_TEMP, "Initrd-fix")
ADB_PORT = 58526
ADB_HOST = "127.0.0.1"
ADB_DEVICE = f"{ADB_HOST}:{ADB_PORT}"
CREATE_NO_WINDOW = 0x08000000
DEBUG = False

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
    "android.permission.PROCESS_OUTGOING_CALLS", "android.permission.UPDATE_LOCK",
    "android.permission.MOUNT_UNMOUNT_FILESYSTEMS",
    "android.permission.ACCESS_FM_RADIO", "android.permission.BROADCAST_PHONE_INTENT",
    "android.permission.PERFORM_SMS_AUTH",
}

DANGEROUS_KEYWORDS = (
    "CAMERA", "RECORD_AUDIO", "READ_CONTACTS", "WRITE_CONTACTS",
    "READ_CALL_LOG", "WRITE_CALL_LOG", "READ_CALENDAR", "WRITE_CALENDAR",
    "READ_SMS", "SEND_SMS", "RECEIVE_SMS", "RECEIVE_MMS",
    "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION",
    "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE",
    "READ_MEDIA_IMAGES", "READ_MEDIA_VIDEO", "READ_MEDIA_AUDIO",
    "BLUETOOTH_CONNECT", "BLUETOOTH_SCAN", "BLUETOOTH_ADVERTISE",
    "READ_PHONE_NUMBERS", "ANSWER_PHONE_CALLS", "NEARBY_WIFI_DEVICES",
    "UWB_RANGING", "BODY_SENSORS", "ACTIVITY_RECOGNITION",
    "POST_NOTIFICATIONS", "SYSTEM_ALERT_WINDOW",
)


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
        with open(archive_path, "wb") as f:
            f.write(new_data)
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
        with open(archive_path, "wb") as f:
            f.write(before_trailer)
            f.write(new_entry)
            f.write(trailer)

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
        with open(archive_path, "wb") as f:
            f.write(before_trailer)
            f.write(new_entry)
            f.write(trailer)

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
        with open(archive_path, "wb") as f:
            for part in parts:
                f.write(part)

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
        with open(archive_path, "wb") as f:
            for part in parts:
                f.write(part)


class ApkAnalyzer:

    @staticmethod
    def _run_aaptpp(args):
        if not os.path.exists(AAPT_PP):
            return ""
        try:
            cmd_input = f"{args}\n"
            r = subprocess.run(
                [AAPT_PP], input=cmd_input, capture_output=True, text=True,
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
        raw = ApkAnalyzer._run_aaptpp(f"package {apk_path}")
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
        raw = ApkAnalyzer._run_aaptpp(f"app-name {apk_path}")
        label = raw.strip().split("\n")[-1].strip() if raw else ""
        if label:
            _debug(f"  -> {label}")
            return label
        return Path(apk_path).stem

    @staticmethod
    def get_permissions(apk_path):
        _debug(f"ApkAnalyzer.get_permissions({os.path.basename(apk_path)})")
        raw = ApkAnalyzer._run_aaptpp(f"permissions {apk_path}")
        if not raw:
            return []
        perms = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.startswith("android.permission.") or line.startswith("com."):
                perms.append(line)
        _debug(f"  -> {len(perms)} permissions")
        return perms

    @staticmethod
    def classify_permission(perm_name):
        if perm_name in PRIVILEGED_PERMS:
            return "privileged"
        perm_upper = perm_name.upper()
        for kw in DANGEROUS_KEYWORDS:
            if kw in perm_upper:
                return "dangerous"
        return "normal"

    @staticmethod
    def get_all_info(apk_path):
        _debug(f"ApkAnalyzer.get_all_info({os.path.basename(apk_path)})")
        pkg = ApkAnalyzer.get_package_name(apk_path)
        label = ApkAnalyzer.get_app_label(apk_path)
        perms = ApkAnalyzer.get_permissions(apk_path)
        result = {
            "package": pkg,
            "label": label,
            "apk_path": apk_path,
            "privileged": [],
            "dangerous": [],
            "normal": [],
        }
        for p in perms:
            cat = ApkAnalyzer.classify_permission(p)
            result[cat].append(p)
        _debug(f"  privileged={len(result['privileged'])}, "
               f"dangerous={len(result['dangerous'])}, "
               f"normal={len(result['normal'])}")
        return result


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
        return 0

    def is_stock(self):
        result = not self.has_info_json()
        _debug(f"is_stock() -> {result}")
        return result

    def is_twrp_supported(self):
        info = self.read_info()
        if info is None:
            result = False
        else:
            raw = info.get("twrp_support", "false")
            if isinstance(raw, str):
                result = raw.strip().lower() == "true"
            else:
                result = bool(raw)
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
                    entries_to_add.append((arcname, data, 0o100644))
            if not entries_to_add:
                raise RuntimeError("TWRP archive is empty")
            existing = {}
            for name, _ds, _sz, _hp in CpioUtils.scan_entries(self.path):
                existing[name] = True
            new_entries = []
            replace_entries = []
            for arcname, data, mode in entries_to_add:
                if arcname in existing:
                    replace_entries.append((arcname, data, mode))
                else:
                    new_entries.append((arcname, data, mode))
            for arcname, data, _mode in replace_entries:
                CpioUtils.delete_file(self.path, arcname)
            if new_entries:
                CpioUtils.add_files(self.path, new_entries)
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
        basename = os.path.basename(src_path)
        if basename == "init" and "init" in existing and "init_orig" not in existing:
            _log(f"Renaming /init -> /init_orig")
            for name, ds, sz, hp in CpioUtils.scan_entries(self.path):
                if name == "/init" or name == "init":
                    orig_data = CpioUtils.read_file(self.path, name)
                    if orig_data:
                        CpioUtils.add_file(self.path, "/init_orig", orig_data)
                        _log(f"  Saved /init_orig ({len(orig_data):,} bytes)")
                    break
        if arcname in existing:
            _debug(f"  Replacing existing: {arcname}")
            CpioUtils.delete_file(self.path, arcname)
        CpioUtils.add_file(self.path, arcname, data)
        _log(f"Injected {arcname} ({len(data):,} bytes)")

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
                entries_to_add.append((arcname, data, 0o100644))
        existing = {name for name, *_ in CpioUtils.scan_entries(self.path)}
        has_init = any(a.split("/")[-1] == "init" for a, _, _ in entries_to_add)
        if has_init and "init" in existing and "init_orig" not in existing:
            _log(f"Renaming /init -> /init_orig")
            for name, ds, sz, hp in CpioUtils.scan_entries(self.path):
                if name == "/init" or name == "init":
                    orig_data = CpioUtils.read_file(self.path, name)
                    if orig_data:
                        CpioUtils.add_file(self.path, "/init_orig", orig_data)
                        _log(f"  Saved /init_orig ({len(orig_data):,} bytes)")
                    break
        new_entries = []
        for arcname, data, mode in entries_to_add:
            if arcname in existing:
                _debug(f"  Replacing existing: {arcname}")
                CpioUtils.delete_file(self.path, arcname)
            new_entries.append((arcname, data, mode))
        if new_entries:
            CpioUtils.add_files(self.path, new_entries)
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

                for item in patch:
                    if "rename" in item:
                        orig_name = item.get("original-name", "").strip("/")
                        rename_to = item["rename"].strip("/")
                        if not orig_name:
                            _debug(f"  SKIP rename: missing original-name")
                            continue
                        if rename_to in existing:
                            _log(f"/{rename_to} already exists, skip rename")
                        elif orig_name not in existing:
                            _debug(f"  SKIP rename: /{orig_name} not found in cpio")
                        else:
                            _log(f"Renaming /{orig_name} -> /{rename_to}")
                            for name, ds, sz, hp in CpioUtils.scan_entries(self.path):
                                if name == f"/{orig_name}" or name == orig_name:
                                    orig_data = CpioUtils.read_file(self.path, name)
                                    if orig_data:
                                        CpioUtils.add_file(self.path, f"/{rename_to}", orig_data)
                                        _log(f"  Saved /{rename_to} ({len(orig_data):,} bytes)")
                                    break

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
                                entries_to_add.append((arcname, data, 0o100644))
                                _debug(f"      -> {arcname} ({len(data):,} bytes)")
                    elif os.path.isfile(pick_full):
                        arcname = f"{drop}/{os.path.basename(pick)}".strip("/")
                        with open(pick_full, "rb") as f:
                            data = f.read()
                        entries_to_add.append((arcname, data, 0o100644))
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
        if os.path.exists(FIX_TEMP):
            shutil.rmtree(FIX_TEMP, ignore_errors=True)
        os.makedirs(FIX_TEMP, exist_ok=True)
        try:
            subprocess.run(
                [SEVEN_ZIP, "x", ASSET_FIX_7Z, f"-o{FIX_TEMP}", "-y"],
                capture_output=True, timeout=30,
                creationflags=CREATE_NO_WINDOW)

            _log("Adding Magisk hook infrastructure")

            init_data = CpioUtils.read_file(self.path, "init")
            if init_data:
                CpioUtils.delete_file(self.path, "init")
                CpioUtils.add_file(self.path, "/wsainit", init_data)
                _log(f"  /init -> /wsainit ({len(init_data):,} bytes)")

            lspinit_path = os.path.join(FIX_TEMP, "lspinit")
            if os.path.exists(lspinit_path):
                with open(lspinit_path, "rb") as f:
                    lspinit_data = f.read()
                CpioUtils.add_file(self.path, "/lspinit", lspinit_data)
                _log(f"  /lspinit ({len(lspinit_data):,} bytes)")

            CpioUtils.add_symlink(self.path, "/init", "lspinit")
            _log(f"  /init -> symlink -> lspinit")

            skip = {"init", "lspinit", "wsainit"}
            existing = {name for name, *_ in CpioUtils.scan_entries(self.path)}
            count = 0
            for root, _dirs, files in os.walk(FIX_TEMP):
                for fname in files:
                    if fname in skip:
                        continue
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, FIX_TEMP).replace("\\", "/")
                    if arcname in existing:
                        CpioUtils.delete_file(self.path, arcname)
                    with open(full, "rb") as f:
                        data = f.read()
                    CpioUtils.add_file(self.path, arcname, data)
                    _log(f"  {arcname} ({len(data):,} bytes)")
                    count += 1
            _log(f"Injected {count + 3} files from fix.7z")
            return True
        finally:
            shutil.rmtree(FIX_TEMP, ignore_errors=True)

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
    def generate_privapp_xml(package_name, privapp_perms):
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            "<permissions>",
            f'    <privapp-permissions package="{package_name}">',
        ]
        for perm in privapp_perms:
            lines.append(f'        <permission name="{perm}"/>')
        lines.append("    </privapp-permissions>")
        lines.append("</permissions>")
        return "\n".join(lines)

    @staticmethod
    def generate_default_xml(package_name, runtime_perms):
        lines = [
            "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>",
            "<exceptions>",
            f'    <exception package="{package_name}">',
        ]
        for perm in runtime_perms:
            lines.append(f'        <permission name="{perm}" fixed="false"/>')
        lines.append("    </exception>")
        lines.append("</exceptions>")
        return "\n".join(lines)

    def create_lsp_image(self, apk_paths, permission_profiles=None):
        _debug(f"create_lsp_image({len(apk_paths)} APKs)")
        if permission_profiles is None:
            permission_profiles = {}
        if os.path.exists(LSP_TEMP):
            shutil.rmtree(LSP_TEMP, ignore_errors=True)
        os.makedirs(LSP_TEMP, exist_ok=True)
        try:
            module_prop = (
                "id=wsa-installer\n"
                "name=WSA Installer\n"
                "version=v1.0\n"
                "versionCode=1\n"
                "author=Mr CYBER\n"
                "description=System app installer for WSA\n"
            )
            with open(os.path.join(LSP_TEMP, "module.prop"), "w") as f:
                f.write(module_prop)
            post_fs_data = (
                "#!/bin/sh\n"
                'BASE="$(dirname "$0")"\n'
                "NVBASE=/data/adb\n"
                "MOD_UPDATE_DIRNAME=modules_update\n"
                'MODULE_UPDATE_ROOT=$NVBASE/$MOD_UPDATE_DIRNAME\n'
                "grep_prop() {\n"
                '    dos2unix <"$2" | sed -n "s/^$1=//p" | head -n 1\n'
                "}\n"
                'MODID=$(grep_prop id "$BASE"/module.prop)\n'
                'MOD_UPDATE_PATH=$MODULE_UPDATE_ROOT/$MODID\n'
                'MOD_PATH=$NVBASE/modules/$MODID\n'
                'mkdir -p -m 0755 "$MOD_PATH"\n'
                'chcon u:object_r:system_file:s0 "$MOD_PATH"\n'
                'cp -dr --preserve=all "$BASE/module.prop" "$MOD_PATH"\n'
                'touch "$MOD_PATH/update"\n'
                'mkdir -p -m 0755 "$MOD_UPDATE_PATH"\n'
                'chcon u:object_r:system_file:s0 "$MOD_UPDATE_PATH"\n'
                'cp -dr --preserve=all "$BASE/module.prop" "$MOD_UPDATE_PATH"\n'
                'cp -dr --preserve=all "$BASE/system" "$MOD_UPDATE_PATH"\n'
            )
            with open(os.path.join(LSP_TEMP, "post-fs-data.sh"), "w") as f:
                f.write(post_fs_data)

            all_privapp = []
            all_runtime = []

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
                    with open(os.path.join(perm_dir, f"{pkg}.json"), "w") as f:
                        json.dump(profile, f, indent=2)
                    _debug(f"  Saved profile: permissions/{pkg}.json")

                    privapp = profile.get("privapp_perms", [])
                    runtime = profile.get("runtime_perms", [])
                    all_privapp.extend(privapp)
                    all_runtime.extend(runtime)

            if all_privapp:
                xml_dir = os.path.join(LSP_TEMP, "system", "etc", "permissions")
                os.makedirs(xml_dir, exist_ok=True)
                xml = self.generate_privapp_xml("wsa-installer", all_privapp)
                with open(os.path.join(xml_dir, "privapp-permissions-wsa-installer.xml"), "w") as f:
                    f.write(xml)
                _debug(f"  Generated privapp-permissions-wsa-installer.xml ({len(all_privapp)} perms)")

            if all_runtime:
                xml_dir = os.path.join(LSP_TEMP, "system", "etc", "default-permissions")
                os.makedirs(xml_dir, exist_ok=True)
                xml = self.generate_default_xml("wsa-installer", all_runtime)
                with open(os.path.join(xml_dir, "default-permissions-wsa-installer.xml"), "w") as f:
                    f.write(xml)
                _debug(f"  Generated default-permissions-wsa-installer.xml ({len(all_runtime)} perms)")

            image_path = os.path.join(LSP_TEMP, LSP_IMAGE_NAME)
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
            image_path = os.path.join(LSP_TEMP, LSP_IMAGE_NAME)
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
        finally:
            shutil.rmtree(LSP_TEMP, ignore_errors=True)

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
    perm_manager_show = Signal(object)


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
        self._signals.perm_manager_show.connect(self._on_perm_manager_show)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_progress)
        self._anim_timer.start(50)

    def _on_log_update(self, msg):
        self._status_text = msg
        self.update()

    def _on_progress_update(self, value):
        self._progress_value = value
        self.update()

    def _on_perm_manager_show(self, widget):
        widget.setParent(self)
        widget.move(
            self.x() + (self.width() - widget.width()) // 2,
            self.y() + (self.height() - widget.height()) // 2,
        )
        widget.show()

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
    result_ready = Signal(dict)
    closed = Signal()


class PermissionManagerWindow(QWidget):

    PM_REF_W = 2000
    PM_REF_H = 2500
    PM_W = 640
    PM_H = 800
    PM_HDR_H = 100
    PM_RADIUS = 30

    def __init__(self, package_name, app_label, permissions_by_category, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(self.PM_W, self.PM_H)
        self.setMouseTracking(True)
        self._package_name = package_name
        self._app_label = app_label
        self._signals = PermissionManagerSignals()
        self._drag_offset = None
        self._hover_btn = None
        self._press_btn = None
        self._chk_hide_uninstall = True
        self._chk_hide_disable = True
        self._privapp_checks = []
        for perm in permissions_by_category.get("privileged", []):
            self._privapp_checks.append({"perm": perm, "checked": True})
        self._runtime_checks = []
        for perm in permissions_by_category.get("dangerous", []):
            self._runtime_checks.append({"perm": perm, "checked": True})
        self._normal_perms = permissions_by_category.get("normal", [])
        self._build_layout()

    def _build_layout(self):
        self._close_rect = (588, 8, 28, 28)
        self._priv_chk_rects = []
        self._run_chk_rects = []
        self._chk_protection = [(80, 152, "uninstall"), (80, 185, "disable")]
        y = 230
        row_h = 26
        for i in range(len(self._privapp_checks)):
            self._priv_chk_rects.append((80, y + i * row_h))
        self._priv_group_y = 210
        self._priv_content_y = y
        y2 = y + max(len(self._privapp_checks), 1) * row_h + 20
        self._run_group_y = y2 - 20
        self._run_content_y = y2
        for i in range(len(self._runtime_checks)):
            self._run_chk_rects.append((80, y2 + i * row_h))
        self._normal_y = y2 + max(len(self._runtime_checks), 1) * row_h + 20
        self._btn_ok_rect = (180, 730, 130, 40)
        self._btn_cancel_rect = (340, 730, 130, 40)

    def _on_ok(self):
        self._signals.result_ready.emit(self.get_result())
        self.close()

    def _on_cancel(self):
        self._signals.closed.emit()
        self.close()

    def get_result(self):
        return {
            "hide_uninstall": self._chk_hide_uninstall,
            "hide_disable": self._chk_hide_disable,
            "privapp_perms": [it["perm"] for it in self._privapp_checks if it["checked"]],
            "runtime_perms": [it["perm"] for it in self._runtime_checks if it["checked"]],
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
        path.addRoundedRect(QRectF(1.5, 1.5, self.PM_REF_W - 3, self.PM_REF_H - 3),
                            self.PM_RADIUS, self.PM_RADIUS)
        return path

    def _header_path(self):
        r = self.PM_RADIUS
        right = self.PM_REF_W - 1.5
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
        sx = self.width() / self.PM_REF_W
        sy = self.height() / self.PM_REF_H
        p.scale(sx, sy)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        outer = self._window_path()
        p.fillPath(outer, MAIN_COLOR)
        p.fillPath(self._header_path(), HEADER_COLOR)
        p.setPen(TITLE_COLOR)
        p.setFont(self._font(38))
        p.drawText(QRectF(80, 25, 1600, 55), Qt.AlignLeft | Qt.AlignVCenter, "Permission Manager")
        pen = QPen(QColor(232, 232, 232), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.drawLine(1934, 31, 1966, 63)
        p.drawLine(1966, 31, 1934, 63)
        p.setPen(TEXT_COLOR)
        p.setFont(self._font(36, QFont.Bold))
        p.drawText(QRectF(80, 120, 1840, 50), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{self._app_label} ({self._package_name})")
        p.setPen(QColor(160, 160, 160))
        p.setFont(self._font(30))
        p.drawText(QRectF(80, 210, 1840, 40), Qt.AlignLeft | Qt.AlignVCenter, "App Protection")
        p.setPen(BORDER_COLOR)
        p.drawRoundedRect(QRectF(60, 240, 1880, 100), 12, 12)
        self._draw_chk(p, 80, 152, self._chk_hide_uninstall, "Hide uninstall button")
        self._draw_chk(p, 80, 185, self._chk_hide_disable, "Hide disable button")
        row_h = 26
        if self._privapp_checks:
            p.setPen(QColor(160, 160, 160))
            p.setFont(self._font(30))
            p.drawText(QRectF(80, self._priv_group_y, 1840, 40), Qt.AlignLeft | Qt.AlignVCenter,
                       f"Privileged Permissions ({len(self._privapp_checks)})")
            grp_h = min(len(self._privapp_checks) * row_h + 16, 260)
            p.setPen(BORDER_COLOR)
            p.drawRoundedRect(QRectF(60, self._priv_group_y + 35, 1880, grp_h), 12, 12)
            p.setClipRect(QRectF(70, self._priv_group_y + 40, 1860, grp_h - 10))
            p.setPen(TEXT_COLOR)
            p.setFont(self._font(26))
            for i, item in enumerate(self._privapp_checks):
                cy = self._priv_content_y + i * row_h
                self._draw_square_chk(p, 80, cy, item["checked"], item["perm"])
            p.setClipping(False)
        if self._runtime_checks:
            p.setPen(QColor(160, 160, 160))
            p.setFont(self._font(30))
            p.drawText(QRectF(80, self._run_group_y, 1840, 40), Qt.AlignLeft | Qt.AlignVCenter,
                       f"Runtime Permissions ({len(self._runtime_checks)})")
            grp_h = min(len(self._runtime_checks) * row_h + 16, 260)
            p.setPen(BORDER_COLOR)
            p.drawRoundedRect(QRectF(60, self._run_group_y + 35, 1880, grp_h), 12, 12)
            p.setClipRect(QRectF(70, self._run_group_y + 40, 1860, grp_h - 10))
            p.setPen(TEXT_COLOR)
            p.setFont(self._font(26))
            for i, item in enumerate(self._runtime_checks):
                cy = self._run_content_y + i * row_h
                self._draw_square_chk(p, 80, cy, item["checked"], item["perm"])
            p.setClipping(False)
        if self._normal_perms:
            p.setPen(QColor(160, 160, 160))
            p.setFont(self._font(30))
            p.drawText(QRectF(80, self._normal_y, 1840, 40), Qt.AlignLeft | Qt.AlignVCenter,
                       f"Normal Permissions ({len(self._normal_perms)}) \u2014 always granted")
            p.setPen(QColor(120, 120, 120))
            p.setFont(self._font(24))
            txt = "  \u00b7  ".join(self._normal_perms[:6])
            if len(self._normal_perms) > 6:
                txt += "  \u00b7  ..."
            p.drawText(QRectF(100, self._normal_y + 45, 1800, 35), Qt.AlignLeft | Qt.AlignVCenter, txt)
        self._draw_btn(p, self._btn_ok_rect, "OK", True)
        self._draw_btn(p, self._btn_cancel_rect, "Cancel", False)
        border_pen = QPen(BORDER_COLOR, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(border_pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(outer)
        p.end()

    def _draw_square_chk(self, p, x, y, checked, text):
        p.save()
        if checked:
            p.setBrush(PROGRESS_FILL)
            p.setPen(PROGRESS_FILL)
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(120, 120, 120))
        p.drawRoundedRect(QRectF(x, y, 22, 22), 4, 4)
        if checked:
            p.setPen(QColor(255, 255, 255))
            p.setFont(self._font(16, QFont.Bold))
            p.drawText(QRectF(x, y, 22, 22), Qt.AlignCenter, "\u2713")
        p.setPen(TEXT_COLOR)
        p.setFont(self._font(26))
        p.drawText(QRectF(x + 32, y, 1780, 22), Qt.AlignLeft | Qt.AlignVCenter, text)
        p.restore()

    def _draw_chk(self, p, x, y, checked, text):
        p.save()
        if checked:
            p.setBrush(PROGRESS_FILL)
            p.setPen(PROGRESS_FILL)
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(120, 120, 120))
        p.drawRoundedRect(QRectF(x, y, 28, 28), 5, 5)
        if checked:
            p.setPen(QColor(255, 255, 255))
            p.setFont(self._font(18, QFont.Bold))
            p.drawText(QRectF(x, y, 28, 28), Qt.AlignCenter, "\u2713")
        p.setPen(TEXT_COLOR)
        p.setFont(self._font(30))
        p.drawText(QRectF(x + 40, y, 800, 28), Qt.AlignLeft | Qt.AlignVCenter, text)
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
        p.drawRoundedRect(QRectF(x, y, w, h), 10, 10)
        p.setPen(QColor(255, 255, 255) if is_ok else TEXT_COLOR)
        p.setFont(self._font(30, QFont.Bold))
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
        for i, (cx, cy) in enumerate(self._priv_chk_rects):
            if cx <= ref.x() <= cx + 200 and cy <= ref.y() <= cy + 26:
                return f"priv_{i}"
        for i, (cx, cy) in enumerate(self._run_chk_rects):
            if cx <= ref.x() <= cx + 200 and cy <= ref.y() <= cy + 26:
                return f"run_{i}"
        for cx, cy, tag in self._chk_protection:
            if cx <= ref.x() <= cx + 400 and cy <= ref.y() <= cy + 28:
                return f"prot_{tag}"
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        sx = self.PM_REF_W / self.PM_W
        sy = self.PM_REF_H / self.PM_H
        pos = event.position()
        ref = QPoint(round(pos.x() * sx), round(pos.y() * sy))
        hit = self._hit_test(ref)
        if hit == "close":
            self._on_cancel()
        elif hit == "ok":
            self._on_ok()
        elif hit == "cancel":
            self._on_cancel()
        elif hit and hit.startswith("priv_"):
            idx = int(hit.split("_")[1])
            self._privapp_checks[idx]["checked"] = not self._privapp_checks[idx]["checked"]
            self.update()
        elif hit and hit.startswith("run_"):
            idx = int(hit.split("_")[1])
            self._runtime_checks[idx]["checked"] = not self._runtime_checks[idx]["checked"]
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
        sx = self.PM_REF_W / self.PM_W
        sy = self.PM_REF_H / self.PM_H
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
            log("Installing TWRP...")
            time.sleep(0.5)

            if is_wsa_img:
                log("Stopping WSA...")
                KillWSA.kill_all()
                time.sleep(3)
            else:
                _debug("  Skipping WSA kill (not WSA img)")
                log("Patching file directly...")

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
            log("Run without --enable-twrp to install first")
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

    def install_as_system_app(self, apk_paths, target_initrd=None):
        return self._launch_gui(self._flow_install_system_app, dict(
            apk_paths=apk_paths,
            target_initrd=target_initrd,
        ))

    def _flow_install_system_app(self, log, window, apk_paths, target_initrd=None):
        _debug("_flow_install_system_app() started")
        _debug(f"  apk_paths: {apk_paths}")

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

        log("Reading APK permissions...")
        apk_infos = []
        for apk_path in apk_paths:
            info = ApkAnalyzer.get_all_info(apk_path)
            apk_infos.append(info)
            log(f"  {info['label']} ({info['package']})")
            log(f"    Privileged: {len(info['privileged'])}, "
                f"Runtime: {len(info['dangerous'])}, "
                f"Normal: {len(info['normal'])}")
            time.sleep(0.3)
        time.sleep(0.5)

        permission_profiles = {}
        for info in apk_infos:
            log(f"Permission manager: {info['label']}")
            categories = {
                "privileged": info["privileged"],
                "dangerous": info["dangerous"],
                "normal": info["normal"],
            }
            perm_result = [None]
            perm_event = threading.Event()

            def _on_perm_result(result, _r=perm_result, _e=perm_event):
                _r[0] = result
                _e.set()

            def _on_perm_closed(_e=perm_event):
                _e.set()

            dlg = PermissionManagerWindow(
                package_name=info["package"],
                app_label=info["label"],
                permissions_by_category=categories,
            )
            dlg._signals.result_ready.connect(_on_perm_result)
            dlg._signals.closed.connect(_on_perm_closed)
            window._signals.perm_manager_show.emit(dlg)
            perm_event.wait()

            if perm_result[0] is None:
                log(f"Skipped {info['package']}")
                continue
            profile = perm_result[0]
            permission_profiles[info["package"]] = profile
            log(f"  Uninstall: {'hidden' if profile['hide_uninstall'] else 'visible'}")
            log(f"  Disable: {'hidden' if profile['hide_disable'] else 'visible'}")
            log(f"  Privapp: {len(profile['privapp_perms'])} permissions")
            log(f"  Runtime: {len(profile['runtime_perms'])} permissions")
            time.sleep(0.3)
        time.sleep(0.5)

        if is_wsa_img:
            log("Stopping WSA...")
            KillWSA.kill_all()
            time.sleep(3)
        else:
            log("Patching file directly...")

        hook_ok = initrd.add_hook_infrastructure()
        if not hook_ok:
            log("Failed to add hook infrastructure!")
            time.sleep(2)
            window.request_close()
            return
        time.sleep(0.5)

        for apk_path in apk_paths:
            pkg = ApkAnalyzer.get_package_name(apk_path)
            profile = permission_profiles.get(pkg)
            if not profile:
                log(f"Skipped {pkg} (no profile)")
                continue
            log(f"Installing {pkg} as system app")
            time.sleep(0.5)

            if initrd.has_lsp_image():
                _debug("lsp image exists, checking for duplicate")
                existing = initrd.find_existing_apks()
                apk_basename = os.path.basename(apk_path)
                found = False
                for existing_pkg, existing_apk in existing:
                    if os.path.basename(existing_apk) == apk_basename:
                        log(f"{pkg} already installed, skip")
                        found = True
                        break
                if found:
                    continue

                _debug("Extracting existing image")
                extract_dir = initrd.extract_lsp_image()
                if extract_dir:
                    priv_app = os.path.join(extract_dir, "system", "priv-app")
                    os.makedirs(os.path.join(priv_app, pkg), exist_ok=True)
                    shutil.copy2(apk_path, os.path.join(priv_app, pkg, os.path.basename(apk_path)))
                    _debug(f"Added: system/priv-app/{pkg}/{os.path.basename(apk_path)}")

                    perm_dir = os.path.join(extract_dir, "permissions")
                    os.makedirs(perm_dir, exist_ok=True)
                    with open(os.path.join(perm_dir, f"{pkg}.json"), "w") as f:
                        json.dump(profile, f, indent=2)

                    privapp_perms = profile.get("privapp_perms", [])
                    runtime_perms = profile.get("runtime_perms", [])
                    if privapp_perms:
                        etc_perms = os.path.join(extract_dir, "system", "etc", "permissions")
                        os.makedirs(etc_perms, exist_ok=True)
                        xml = InitrdManager.generate_privapp_xml("wsa-installer", privapp_perms)
                        with open(os.path.join(etc_perms, "privapp-permissions-wsa-installer.xml"), "w") as f:
                            f.write(xml)
                    if runtime_perms:
                        etc_def = os.path.join(extract_dir, "system", "etc", "default-permissions")
                        os.makedirs(etc_def, exist_ok=True)
                        xml = InitrdManager.generate_default_xml("wsa-installer", runtime_perms)
                        with open(os.path.join(etc_def, "default-permissions-wsa-installer.xml"), "w") as f:
                            f.write(xml)

                    initrd.repack_lsp_image()
                    log(f"Added {pkg}")
                else:
                    log("Failed to extract image, creating new")
                    image_data = initrd.create_lsp_image([apk_path], {pkg: profile})
                    arcname = f"overlay.d/sbin/{LSP_IMAGE_NAME}"
                    if CpioUtils.has_file(initrd.path, arcname):
                        CpioUtils.delete_file(initrd.path, arcname)
                    CpioUtils.add_file(initrd.path, arcname, image_data)
                    log(f"Added {pkg}")
            else:
                _debug("No lsp image, creating new")
                image_data = initrd.create_lsp_image([apk_path], {pkg: profile})
                arcname = f"overlay.d/sbin/{LSP_IMAGE_NAME}"
                CpioUtils.add_file(initrd.path, arcname, image_data)
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
    global DEBUG
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  twrp.py                                              Auto-inject + boot TWRP
  twrp.py --path C:\\initrd.img                         Patch specific file
  twrp.py --status                                     Check WSA status
  twrp.py --status --path C:\\initrd.img               Check specific file
  twrp.py --enable-twrp                                Set recovery flag
  twrp.py --enable-twrp --path C:\\initrd.img          Set flag in file
  twrp.py --disable-twrp                               Clear recovery flag
  twrp.py --disable-twrp --path C:\\initrd.img         Clear flag in file
  twrp.py --inject-file info.json                      Inject file
  twrp.py --inject-file info.json into /info/          Inject into subfolder
  twrp.py --inject-folder assest/twrp/                 Inject folder
  twrp.py --inject assets/test.7z                      Extract 7z + patch.json
  twrp.py --install-as-system-app app.apk              Install APK as system app
  twrp.py --install-as-system-app a.apk b.apk          Install multiple APKs
        """)
    parser.add_argument("--status", action="store_true",
                        help="Check WSA and TWRP status")
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
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug output")
    args = parser.parse_args()

    if args.debug:
        DEBUG = True
        _debug("Debug mode enabled")

    _debug(f"args: status={args.status}, path={args.path}, enable={args.enable_twrp}, "
           f"disable={args.disable_twrp}, inject_file={args.inject_file}, "
           f"inject_folder={args.inject_folder}, inject={args.inject}, "
           f"install_as_system_app={args.install_as_system_app}")

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
        )
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
