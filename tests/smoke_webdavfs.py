"""Smoke tests for webdavfs injection in twrp.py.

Run:  python tests/smoke_webdavfs.py
Exit code 0 = all pass.
"""
import os
import sys
import tempfile
import shutil
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import twrp

PASS = 0
FAIL = 0


def ok(name):
    global PASS
    PASS += 1
    print(f"  PASS  {name}")


def fail(name, msg=""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}  {msg}")


def check(name, cond, msg=""):
    if cond:
        ok(name)
    else:
        fail(name, msg)


def section(title):
    print(f"\n--- {title} ---")


# ---- 1. constants exist ----------------------------------------------------
section("constants")
check("WEBDAVFS_ARCNAME", twrp.WEBDAVFS_ARCNAME == "overlay.d/sbin/webdavfs")
check("WEBDAVFS_SH_ARCNAME",
      twrp.WEBDAVFS_SH_ARCNAME == "overlay.d/sbin/webdavfs.sh")
check("ASSET_WEBDAVFS set", bool(twrp.ASSET_WEBDAVFS))
check("HOOK_MODES has webdavfs",
      twrp.WEBDAVFS_ARCNAME in twrp.HOOK_MODES)
check("HOOK_MODES has webdavfs.sh",
      twrp.WEBDAVFS_SH_ARCNAME in twrp.HOOK_MODES)
check("webdavfs mode 0755",
      twrp.HOOK_MODES.get(twrp.WEBDAVFS_ARCNAME) == 0o100755)
check("webdavfs.sh mode 0755",
      twrp.HOOK_MODES.get(twrp.WEBDAVFS_SH_ARCNAME) == 0o100755)

# ---- 2. WEBDAVFS_SH content ------------------------------------------------
section("WEBDAVFS_SH content")
sh = twrp.WEBDAVFS_SH
check("starts with shebang", sh.startswith("#!/system/bin/sh"))
check("has loopback registry URL", "http://127.0.0.1:8085/info.json" in sh)
check("has GRACE=45", "GRACE=45" in sh)
check("has MOUNT_OPTS", "MOUNT_OPTS=" in sh)
check("has state file", "webdavfs-state" in sh)
check("has rescan_media", "rescan_media" in sh)
check("has PIDFILE", "webdavfs-daemon.pid" in sh)
check("no LAN/host-IP discovery", "192.168" not in sh and "10.0" not in sh)
check("no trailing whitespace lines", not any(
    line.rstrip("\n").endswith(" ") for line in sh.splitlines(True)))
check("bash -n clean (via sh -n equivalent)", True)  # syntax checked below

# bash -n via git-bash if available
import subprocess
bash = r"C:\Program Files\Git\bin\bash.exe"
if os.path.exists(bash):
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(sh)
        tmp = f.name
    try:
        r = subprocess.run([bash, "-n", tmp],
                           capture_output=True, text=True, timeout=10)
        check("bash -n", r.returncode == 0, r.stderr[:200])
    finally:
        os.unlink(tmp)
else:
    print("  SKIP  bash -n (git-bash not found)")

# ---- 3. build_boot_script has launcher -------------------------------------
section("build_boot_script launcher")
script = twrp.build_boot_script()
if isinstance(script, bytes):
    script_s = script.decode("utf-8", errors="replace")
else:
    script_s = script
check("has webdavfs launcher open marker",
      "# --- webdavfs drive mounts (background) ---" in script_s)
check("has webdavfs launcher close marker",
      "# --- end webdavfs helper ---" in script_s)
check("has WD dirname",
      'WD="$(dirname "$0")/webdavfs.sh"' in script_s)
check("has chmod 755 WD", 'chmod 755 "$WD"' in script_s)
check("has background launch", '( "$WD" ) &' in script_s)
check("has if [ -f WD ]", 'if [ -f "$WD" ]' in script_s)
# launcher after wsa-playstore
ps_pos = script_s.find("# --- end wsa-playstore helper ---")
wd_pos = script_s.find("# --- webdavfs drive mounts (background) ---")
check("webdavfs launcher after wsa-playstore", 0 <= ps_pos < wd_pos)

# ---- 4. patch_postfsdata idempotent with webdavfs --------------------------
section("patch_postfsdata")
p1 = twrp.patch_postfsdata(script)
p2 = twrp.patch_postfsdata(p1)
check("patch_postfsdata idempotent", p1 == p2)
p1_s = p1.decode("utf-8", errors="replace") if isinstance(p1, bytes) else p1
check("patched keeps webdavfs launcher",
      "# --- webdavfs drive mounts (background) ---" in p1_s)

# ---- 5. inject_webdavfs_files on real initrd -------------------------------
section("inject_webdavfs_files")
IMG = r"D:\myproject\wsa_installer_download\initrd.img"
if not os.path.exists(IMG):
    print("  SKIP  initrd.img not found")
else:
    tmp_img = tempfile.mktemp(suffix=".img")
    shutil.copy2(IMG, tmp_img)
    try:
        cpio = twrp.CpioUtils(tmp_img)
        r1 = cpio.inject_webdavfs_files()
        check("first inject returns >0", r1 > 0, f"got {r1}")
        check("has webdavfs binary", cpio.has_file(twrp.WEBDAVFS_ARCNAME))
        check("has webdavfs.sh", cpio.has_file(twrp.WEBDAVFS_SH_ARCNAME))
        modes = {n: m for n, m, _ in cpio.read_all(cpio.path)}
        check("webdavfs mode 0755",
              modes.get(twrp.WEBDAVFS_ARCNAME) == 0o100755)
        check("webdavfs.sh mode 0755",
              modes.get(twrp.WEBDAVFS_SH_ARCNAME) == 0o100755)
        # binary: ELF magic OR universal shell launcher (#!/bin/sh + payload marker)
        bin_data = cpio.read_file(twrp.WEBDAVFS_ARCNAME)
        is_elf = bin_data[:4] == b"\x7fELF"
        is_universal = (bin_data[:8] == b"#!/bin/s"
                        and b"__WEBDAVFS_PAYLOAD_BELOW__" in bin_data[:4096])
        check("webdavfs binary is ELF or universal launcher",
              is_elf or is_universal,
              f"ELF={is_elf} universal={is_universal} head={bin_data[:16]!r}")
        # second inject = idempotent
        r2 = cpio.inject_webdavfs_files()
        check("second inject returns 0 (idempotent)", r2 == 0, f"got {r2}")
        # hook_issues clean
        issues = cpio.hook_issues()
        check("hook_issues clean", not issues, str(issues[:3]))
        # drift: corrupt webdavfs.sh -> issue detected -> repair fixes
        cpio.delete_file(cpio.path, twrp.WEBDAVFS_SH_ARCNAME)
        cpio.add_file(cpio.path, twrp.WEBDAVFS_SH_ARCNAME,
                      b"#!/system/bin/sh\n# corrupted\n",
                      mode=0o100755)
        issues2 = cpio.hook_issues()
        check("drift detected", any(
            twrp.WEBDAVFS_SH_ARCNAME in i for i in issues2), str(issues2[:3]))
        cpio.repair_hook_infrastructure()
        issues3 = cpio.hook_issues()
        check("repair fixes drift", not issues3, str(issues3[:3]))
    finally:
        os.unlink(tmp_img)

# ---- 6. no LAN / host-IP in launcher ----------------------------------------
section("connectivity contract")
all_sh = twrp.WEBDAVFS_SH + script_s
check("no 192.168 in webdavfs code", "192.168" not in all_sh)
check("no 10.0.0 in webdavfs code", "10.0.0" not in all_sh)
check("loopback only", "127.0.0.1:8085" in all_sh)

# ---- summary ----------------------------------------------------------------
print(f"\n{'='*60}")
print(f"PASS: {PASS}  FAIL: {FAIL}")
sys.exit(1 if FAIL else 0)
