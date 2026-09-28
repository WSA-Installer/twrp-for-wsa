# The Boot Dispatcher (`init.c`)

> `init.c` is compiled into a **statically linked x86_64 Linux ELF** and injected
> as `/init` inside `initrd.img`. The kernel always starts `/init`, so this
> binary decides on every boot whether WSA starts TWRP or Android.

Source: [`init.c`](../init.c) · CI: [`.github/workflows/build-dispatcher.yml`](../.github/workflows/build-dispatcher.yml) ·
Binary: [`prebuilt/init`](../prebuilt/init)

---

## Boot chain

```
kernel
  └─ /init                        ← this dispatcher (compiled from init.c)
       ├─ recovery_flag == "true"  → exec /sbin/twrp          (recovery)
       ├─ /lspinit executable      → exec /lspinit            (normal boot)
       ├─ /wsainit executable      → exec /wsainit            (normal boot)
       └─ neither                  → log + exit 1
```

* The flag is read from **`/info.json`** inside the ramdisk, field
  `recovery_flag`.
* Matching is **case-insensitive** and tolerant of spacing:
  `cistrstr(buf, "\"recovery_flag\": \"true\"")`.
* The original `/init` is **never renamed** — no `init_orig` is created. The
  dispatcher simply replaces it at injection time.
* If `exec /sbin/twrp` fails, the dispatcher **falls through** to the normal
  boot chain instead of hanging.
* `/lspinit` is preferred over `/wsainit`; each is only tried after
  `access(path, X_OK)` confirms it is executable.

### Real initrd layouts handled

| Variant | Files |
|---|---|
| NoGApps | `/init` (2 MB ELF), `/info.json` |
| GApps / Magisk | `/init` (symlink → `lspinit`), `/lspinit`, `/wsainit`, `/info.json`, `/overlay.d/sbin/*` |

After injection: `/init` = dispatcher, `/sbin/twrp` = TWRP, `/info.json` =
metadata with `recovery_flag`.

---

## Debug logging

`log_open()` / `log_msg()` / `log_close()` write to **two** places:

| Path | When |
|---|---|
| `/tmp/twrp_debug.log` | always — ramdisk tmpfs, readable from TWRP's file manager |
| `/mnt/c/Windows/Temp/twrp_debug.log` | only when `/mnt/c` is mounted — survives a reboot, readable from Windows |

Every run starts with `=== TWRP Dispatcher Debug Log ===` followed by
`--- Dispatcher started ---`, then the `info.json` dump, the flag decision and
the chosen exec target. Failures are logged too:
`ERROR: exec /sbin/twrp FAILED`, `ERROR: exec /lspinit FAILED`,
`ERROR: neither /lspinit nor /wsainit found`.

---

## Building

The dispatcher runs in the Android/WSA ramdisk, so it must be a **static ELF**:
there are no shared libraries available that early in boot.

### Locally (any Linux box)

```bash
sudo apt-get install -y musl-tools
musl-gcc -static -Os -Wall -Wextra -Wno-comment -s -o init init.c
file init
# init: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, ...
```

`-Wno-comment` is used because the header comment contains
`/overlay.d/sbin/*`, which clang/gcc read as a nested block comment
(`warning: '/*' within block comment`). The source itself is left untouched.

### On Windows

No Windows-hosted compiler on this project's machine can emit a Linux ELF
(clang without a sysroot, no mingw/MSVC/NDK target), so the build is done in
GitHub Actions — see below.

### CI (GitHub Actions)

`.github/workflows/build-dispatcher.yml` runs on `ubuntu-latest` and:

1. installs `musl-tools`
2. compiles with `musl-gcc -static -Os -Wall -Wextra -Wno-comment -s`
3. asserts the result: `ELF 64-bit LSB executable`, `x86-64`,
   **statically linked**, and **no `INTERP`/`PT_INTERP`** segment
4. prints `sha256sum`
5. uploads the artifact `dispatcher-init` and (on `main`) commits it to
   `prebuilt/init` with `prebuilt/SHA256SUMS`

Run it with **Actions → Build dispatcher → Run workflow**, or:

```bash
gh workflow run build-dispatcher.yml -R WSA-Installer/twrp-for-wsa
gh run watch   -R WSA-Installer/twrp-for-wsa
gh run download -R WSA-Installer/twrp-for-wsa
```

Verified first build — run
[`36410185473`](https://github.com/WSA-Installer/twrp-for-wsa/actions/runs/36410185473)
(`success`, 2026-09-28):

| Property | Value |
|---|---|
| Command | `musl-gcc -static -Os -Wall -Wextra -Wno-comment -s -o init init.c` |
| Warnings | 1 — `init.c:109: unused parameter 'buf'` (no `-Werror`) |
| Output | `ELF 64-bit LSB executable, x86-64, statically linked, stripped` |
| Size | 29,880 bytes |
| sha256 | `cadae90db6816d2f06425f5c81f59c071fbb06196d3df5823fa8036083f07748` |
| Artifact | `dispatcher-init` (`prebuilt/init`, `prebuilt/SHA256SUMS`) |
| Commit | `a7ba885` — `ci: update prebuilt/init dispatcher binary` |

---

## Verifying a binary

```bash
llvm-readobj --file-headers prebuilt/init     # Class: ELF64, Machine: EM_X86_64
llvm-readobj --program-headers prebuilt/init  # must NOT list INTERP
llvm-objdump -f prebuilt/init
sha256sum -c prebuilt/SHA256SUMS
```

A valid dispatcher is:

| Property | Expected |
|---|---|
| Type | `ELF64` LSB executable (ET_EXEC or ET_DYN static-pie) |
| Machine | `x86-64` |
| Linkage | statically linked — no `interpreter` |
| Size | roughly 15–50 KB after `-s` |
| Strings | `/info.json`, `/sbin/twrp`, `/lspinit`, `/wsainit`, `recovery_flag` |

---

## Injecting it

The dispatcher is placed at `/init` inside `initrd.img` — the same cpio archive
the rest of this project patches (`twrp.py --inject …`, IMG Manager Apply).
The full TWRP workflow also compiles it during
`.github/workflows/build-twrp.yml` ("Compile dispatcher (init)") and packs it
into the recovery ramdisk before creating `twrp.img`.

To toggle the boot path:

```bash
twrp.py --enable-twrp     # set recovery_flag = true  → boots TWRP
twrp.py --disable-twrp    # set recovery_flag = false → boots Android
twrp.py --status          # shows the current flag
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ERROR: /info.json not found or empty` | image was injected without metadata — re-run `--inject` |
| `recovery_flag = false or missing` on a TWRP boot | flag not written; `twrp.py --enable-twrp` |
| `ERROR: exec /sbin/twrp FAILED` | `/sbin/twrp` missing or not executable — check `twrp.py --status` (`Missing TWRP files`) |
| `ERROR: exec /lspinit FAILED` | the binary exists but is not executable (`access(X_OK)` passed yet `exec` failed) — check modes with `--status` / `hook_issues()` |
| `ERROR: neither /lspinit nor /wsainit found` | a GApps/Magisk image without its init chain — re-inject |
| No log written | `/tmp` is not writable and `/mnt/c` is not mounted at that point — open TWRP's file manager and read `/tmp/twrp_debug.log` |
| `warning: '/*' within block comment` when compiling | harmless; suppressed with `-Wno-comment` |

See also: [Architecture](architecture.md) · [Flow](flow.md) · [Developer Guide](developer-guide.md)
