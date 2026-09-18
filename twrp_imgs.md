Absolutely! Here are all **7 variants** with updated `twrp_support: "True"` and detailed TWRP Recovery notes.

---

## 1. GApps — Standard

**Image path**
```
C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0.img
```

**info.json**
```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "True",
  "build_version": "3.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "IMAGE OVERVIEW\nThis WSA 2407.40000.4.0 x64 Release-Nightly image includes Google Apps and retains the standard Amazon configuration. It is a non-root WSA image designed for users who want Google-related Android functionality without Magisk root.\n\nTARGET USERS\nRecommended for users who want a Google-oriented WSA environment for Android applications, testing, development, and general desktop Android usage. It is also suitable for users who do not require root-level system modifications.\n\nKEY BENEFITS\n• Google Apps are included in the image.\n• Standard Amazon configuration is retained.\n• Non-root configuration provides a simpler starting point.\n• Suitable for applications and workflows that require Google components.\n• Useful for general WSA testing and Android application compatibility work.\n\nLIMITATIONS\n• Magisk root is not included.\n• Root-dependent applications and modifications are unavailable by default.\n• Individual applications may still have compatibility requirements beyond the included Google components.\n\nTWRP RECOVERY\nThis image includes TWRP Recovery support for WSA. TWRP (TeamWin Recovery Project) is a custom recovery environment that provides advanced backup, restore, flashing, and maintenance capabilities for the Android system.\n\nHOW IT WORKS IN WSA\nThe WSA boot chain starts with the Linux kernel loading /init, which is a custom dispatcher ELF. On boot, the dispatcher reads /info.json and checks the recovery_flag field. If recovery_flag is set to \"True\", the dispatcher boots into TWRP by executing /overlay.d/sbin/twrp instead of the normal Android init. If recovery_flag is \"false\", it proceeds with the standard WSA boot through lspinit and wsainit into Android.\n\nTo enter TWRP: set recovery_flag to \"True\" and reboot WSA.\nTo exit TWRP: set recovery_flag to \"false\" and reboot WSA.\n\nTWRP CAPABILITIES IN WSA\n• Full system backup and restore (Nandroid backup)\n• Flash custom ZIP files and modifications\n• File manager for browsing and editing system files\n• ADB sideload for installing packages\n• Terminal access for advanced operations\n• Partition management and formatting\n\nWHY USE THIS IMAGE\nChoose this variant when Google Apps are required but Magisk root and a NoAmazon configuration are not needed."
}
```

**Inject**
```powershell
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0.img"
```

**Verify**
```powershell
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0.img"
```

---

## 2. GApps + NoAmazon

**Image path**
```
C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0-NoAmazon.img
```

**info.json**
```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "False",
  "build_version": "3.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "IMAGE OVERVIEW\nThis WSA 2407.40000.4.0 x64 Release-Nightly image includes Google Apps while excluding Amazon Appstore support. It provides a Google-oriented configuration without Magisk root.\n\nTARGET USERS\nRecommended for users who want Google Apps and related Android functionality but do not want Amazon Appstore components. It can be useful for application testing, development, Android software compatibility work, and general WSA usage.\n\nKEY BENEFITS\n• Google Apps are included.\n• Amazon Appstore support is excluded.\n• Non-root configuration provides a straightforward environment.\n• Suitable for users who prefer Google functionality over Amazon integration.\n• Useful for testing applications that require Google components.\n\nLIMITATIONS\n• Magisk root is not included.\n• Root-dependent applications and modifications are unavailable by default.\n• Amazon Appstore functionality is unavailable.\n\nTWRP RECOVERY\nThis image includes TWRP Recovery support for WSA. TWRP (TeamWin Recovery Project) is a custom recovery environment that provides advanced backup, restore, flashing, and maintenance capabilities for the Android system.\n\nHOW IT WORKS IN WSA\nThe WSA boot chain starts with the Linux kernel loading /init, which is a custom dispatcher ELF. On boot, the dispatcher reads /info.json and checks the recovery_flag field. If recovery_flag is set to \"True\", the dispatcher boots into TWRP by executing /overlay.d/sbin/twrp instead of the normal Android init. If recovery_flag is \"false\", it proceeds with the standard WSA boot through lspinit and wsainit into Android.\n\nTo enter TWRP: set recovery_flag to \"True\" and reboot WSA.\nTo exit TWRP: set recovery_flag to \"false\" and reboot WSA.\n\nTWRP CAPABILITIES IN WSA\n• Full system backup and restore (Nandroid backup)\n• Flash custom ZIP files and modifications\n• File manager for browsing and editing system files\n• ADB sideload for installing packages\n• Terminal access for advanced operations\n• Partition management and formatting\n\nWHY USE THIS IMAGE\nChoose this variant when you want Google Apps without Amazon Appstore support and do not require Magisk root. For root functionality, use a Magisk-based variant."
}
```

**Inject**
```powershell
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0-NoAmazon.img"
```

**Verify**
```powershell
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0-NoAmazon.img"
```

---

## 3. Magisk Stable + GApps

**Image path**
```
C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-GApps-13.0.img
```

**info.json**
```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "True",
  "root_method": "Magisk",
  "amazon_support": "True",
  "build_version": "3.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "IMAGE OVERVIEW\nThis WSA 2407.40000.4.0 x64 Release-Nightly image combines Google Apps with Magisk 30.6.30600 stable root support. The standard Amazon configuration is retained.\n\nTARGET USERS\nDesigned for advanced WSA users, developers, testers, and users who require root-based Android customization together with Google Apps.\n\nKEY BENEFITS\n• Google Apps are included.\n• Magisk root support is included.\n• Stable Magisk configuration is identified in the image filename.\n• Suitable for root-enabled applications and system customization.\n• Useful for development, debugging, testing, and advanced WSA experimentation.\n\nLIMITATIONS\n• Root-enabled configurations can require additional troubleshooting.\n• Some applications may behave differently in a rooted environment.\n• Amazon support is retained rather than removed.\n\nTWRP RECOVERY\nThis image includes TWRP Recovery support for WSA. TWRP (TeamWin Recovery Project) is a custom recovery environment that provides advanced backup, restore, flashing, and maintenance capabilities for the Android system.\n\nHOW IT WORKS IN WSA\nThe WSA boot chain starts with the Linux kernel loading /init, which is a custom dispatcher ELF. On boot, the dispatcher reads /info.json and checks the recovery_flag field. If recovery_flag is set to \"True\", the dispatcher boots into TWRP by executing /overlay.d/sbin/twrp instead of the normal Android init. If recovery_flag is \"false\", it proceeds with the standard WSA boot through lspinit and wsainit into Android.\n\nTo enter TWRP: set recovery_flag to \"True\" and reboot WSA.\nTo exit TWRP: set recovery_flag to \"false\" and reboot WSA.\n\nTWRP CAPABILITIES IN WSA\n• Full system backup and restore (Nandroid backup)\n• Flash custom ZIP files and modifications\n• File manager for browsing and editing system files\n• ADB sideload for installing packages\n• Terminal access for advanced operations\n• Partition management and formatting\n\nWHY USE THIS IMAGE\nChoose this variant when you need both Google Apps and Magisk root in the same WSA environment. Users who do not need root should use a non-root GApps variant."
}
```

**Inject**
```powershell
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-GApps-13.0.img"
```

**Verify**
```powershell
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-GApps-13.0.img"
```

---

## 4. NoGApps

**Image path**
```
C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps.img
```

**info.json**
```json
{
  "twrp_support": "True",
  "gapp_support": "False",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "True",
  "build_version": "3.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "IMAGE OVERVIEW\nThis WSA 2407.40000.4.0 x64 Release-Nightly image does not include Google Apps and does not provide Magisk root. Because the filename does not specify NoAmazon, the standard Amazon configuration is retained.\n\nTARGET USERS\nSuitable for users who do not require Google Apps and prefer a non-root WSA environment. It can be useful for testing, development, sideloading, automation, and Android applications that do not depend on Google components.\n\nKEY BENEFITS\n• No Google Apps layer is included.\n• Non-root configuration keeps the environment straightforward.\n• Standard Amazon configuration is retained.\n• Useful for testing and application sideloading.\n• Provides an alternative to GApps-based WSA images.\n\nLIMITATIONS\n• Applications requiring Google Play services or other Google components may not work correctly.\n• Magisk root is not available by default.\n• Root-dependent modifications are unsupported.\n\nTWRP RECOVERY\nThis image includes TWRP Recovery support for WSA. TWRP (TeamWin Recovery Project) is a custom recovery environment that provides advanced backup, restore, flashing, and maintenance capabilities for the Android system.\n\nHOW IT WORKS IN WSA\nThe WSA boot chain starts with the Linux kernel loading /init, which is a custom dispatcher ELF. On boot, the dispatcher reads /info.json and checks the recovery_flag field. If recovery_flag is set to \"True\", the dispatcher boots into TWRP by executing /overlay.d/sbin/twrp instead of the normal Android init. If recovery_flag is \"false\", it proceeds with the standard WSA boot through lspinit and wsainit into Android.\n\nTo enter TWRP: set recovery_flag to \"True\" and reboot WSA.\nTo exit TWRP: set recovery_flag to \"false\" and reboot WSA.\n\nTWRP CAPABILITIES IN WSA\n• Full system backup and restore (Nandroid backup)\n• Flash custom ZIP files and modifications\n• File manager for browsing and editing system files\n• ADB sideload for installing packages\n• Terminal access for advanced operations\n• Partition management and formatting\n\nWHY USE THIS IMAGE\nChoose this variant when you want NoGApps while retaining Amazon support and do not require root. For a NoGApps and NoAmazon configuration, use the corresponding NoAmazon variant."
}
```

**Inject**
```powershell
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps.img"
```

**Verify**
```powershell
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps.img"
```

---

## 5. Magisk Canary + GApps + NoAmazon

**Image path**
```
C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-canary-GApps-13.0-NoAmazon.img
```

**info.json**
```json
{
  "twrp_support": "True",
  "gapp_support": "True",
  "root_support": "True",
  "root_method": "Magisk Canary",
  "amazon_support": "False",
  "build_version": "3.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "IMAGE OVERVIEW\nThis WSA 2407.40000.4.0 x64 Release-Nightly image combines Google Apps with Magisk 30.6.30600 Canary root support and excludes Amazon Appstore support.\n\nTARGET USERS\nDesigned for advanced users, developers, testers, and WSA enthusiasts who specifically want Magisk root, Google Apps, and a NoAmazon configuration.\n\nKEY BENEFITS\n• Google Apps are included.\n• Magisk root support is included.\n• The image uses the Canary Magisk variant identified in its filename.\n• Amazon Appstore support is excluded.\n• Suitable for advanced customization, debugging, development, and root-enabled applications.\n\nLIMITATIONS\n• Canary builds are intended for users comfortable with testing and troubleshooting newer configurations.\n• Root access can introduce application compatibility considerations.\n• Amazon Appstore functionality is unavailable.\n\nTWRP RECOVERY\nThis image includes TWRP Recovery support for WSA. TWRP (TeamWin Recovery Project) is a custom recovery environment that provides advanced backup, restore, flashing, and maintenance capabilities for the Android system.\n\nHOW IT WORKS IN WSA\nThe WSA boot chain starts with the Linux kernel loading /init, which is a custom dispatcher ELF. On boot, the dispatcher reads /info.json and checks the recovery_flag field. If recovery_flag is set to \"True\", the dispatcher boots into TWRP by executing /overlay.d/sbin/twrp instead of the normal Android init. If recovery_flag is \"false\", it proceeds with the standard WSA boot through lspinit and wsainit into Android.\n\nTo enter TWRP: set recovery_flag to \"True\" and reboot WSA.\nTo exit TWRP: set recovery_flag to \"false\" and reboot WSA.\n\nTWRP CAPABILITIES IN WSA\n• Full system backup and restore (Nandroid backup)\n• Flash custom ZIP files and modifications\n• File manager for browsing and editing system files\n• ADB sideload for installing packages\n• Terminal access for advanced operations\n• Partition management and formatting\n\nWHY USE THIS IMAGE\nChoose this variant when you specifically require Google Apps and Magisk Canary root while excluding Amazon components. Users wanting a non-root configuration should use the GApps-NoAmazon variant, while users wanting stable Magisk should use the stable Magisk build."
}
```

**Inject**
```powershell
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-canary-GApps-13.0-NoAmazon.img"
```

**Verify**
```powershell
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-canary-GApps-13.0-NoAmazon.img"
```

---

## 6. Magisk Stable + NoGApps + NoAmazon

**Image path**
```
C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-NoGApps-NoAmazon.img
```

**info.json**
```json
{
  "twrp_support": "True",
  "gapp_support": "False",
  "root_support": "True",
  "root_method": "Magisk",
  "amazon_support": "False",
  "build_version": "3.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "IMAGE OVERVIEW\nThis WSA 2407.40000.4.0 x64 Release-Nightly image provides Magisk 30.6.30600 stable root support while excluding Google Apps and Amazon Appstore support.\n\nTARGET USERS\nDesigned for advanced users, developers, testers, and users who need root-based WSA customization without Google or Amazon components.\n\nKEY BENEFITS\n• Magisk root support is included.\n• Stable Magisk configuration is identified in the filename.\n• Google Apps are excluded.\n• Amazon Appstore support is excluded.\n• Suitable for root-enabled applications, development, debugging, and system experimentation.\n\nLIMITATIONS\n• Google Play services and applications requiring Google components may not work correctly.\n• Amazon Appstore functionality is unavailable.\n• Root configurations may require additional troubleshooting.\n\nTWRP RECOVERY\nThis image includes TWRP Recovery support for WSA. TWRP (TeamWin Recovery Project) is a custom recovery environment that provides advanced backup, restore, flashing, and maintenance capabilities for the Android system.\n\nHOW IT WORKS IN WSA\nThe WSA boot chain starts with the Linux kernel loading /init, which is a custom dispatcher ELF. On boot, the dispatcher reads /info.json and checks the recovery_flag field. If recovery_flag is set to \"True\", the dispatcher boots into TWRP by executing /overlay.d/sbin/twrp instead of the normal Android init. If recovery_flag is \"false\", it proceeds with the standard WSA boot through lspinit and wsainit into Android.\n\nTo enter TWRP: set recovery_flag to \"True\" and reboot WSA.\nTo exit TWRP: set recovery_flag to \"false\" and reboot WSA.\n\nTWRP CAPABILITIES IN WSA\n• Full system backup and restore (Nandroid backup)\n• Flash custom ZIP files and modifications\n• File manager for browsing and editing system files\n• ADB sideload for installing packages\n• Terminal access for advanced operations\n• Partition management and formatting\n\nWHY USE THIS IMAGE\nChoose this variant when Magisk root is the primary requirement and Google Apps and Amazon Appstore are not needed. Users who need Google Apps should select a Magisk-GApps variant, while users who do not need root should select a non-root NoGApps-NoAmazon image."
}
```

**Inject**
```powershell
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-NoGApps-NoAmazon.img"
```

**Verify**
```powershell
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-NoGApps-NoAmazon.img"
```

---

## 7. NoGApps + NoAmazon

**Image path**
```
C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps-NoAmazon.img
```

**info.json**
```json
{
  "twrp_support": "True",
  "gapp_support": "False",
  "root_support": "False",
  "root_method": "Unknown",
  "amazon_support": "False",
  "build_version": "3.1.0",
  "wsa_version": "2407.40000.4.0",
  "recovery_flag": "False",
  "note": "IMAGE OVERVIEW\nThis WSA 2407.40000.4.0 x64 Release-Nightly image is a minimal, non-root configuration without Google Apps or Amazon Appstore support.\n\nTARGET USERS\nRecommended for users who want a clean WSA environment without Google or Amazon integration. It is suitable for testing, development, automation, application sideloading, and users who do not require Google services or root functionality.\n\nKEY BENEFITS\n• Google Apps are excluded.\n• Amazon Appstore support is excluded.\n• No Magisk root configuration is included.\n• Provides a simple base for WSA testing and customization.\n• Avoids optional Google and Amazon integrations.\n\nLIMITATIONS\n• Applications requiring Google Play services may not function correctly.\n• Amazon Appstore functionality is unavailable.\n• Root-dependent applications and modifications are not supported by default.\n\nTWRP RECOVERY\nThis image includes TWRP Recovery support for WSA. TWRP (TeamWin Recovery Project) is a custom recovery environment that provides advanced backup, restore, flashing, and maintenance capabilities for the Android system.\n\nHOW IT WORKS IN WSA\nThe WSA boot chain starts with the Linux kernel loading /init, which is a custom dispatcher ELF. On boot, the dispatcher reads /info.json and checks the recovery_flag field. If recovery_flag is set to \"True\", the dispatcher boots into TWRP by executing /overlay.d/sbin/twrp instead of the normal Android init. If recovery_flag is \"false\", it proceeds with the standard WSA boot through lspinit and wsainit into Android.\n\nTo enter TWRP: set recovery_flag to \"True\" and reboot WSA.\nTo exit TWRP: set recovery_flag to \"false\" and reboot WSA.\n\nTWRP CAPABILITIES IN WSA\n• Full system backup and restore (Nandroid backup)\n• Flash custom ZIP files and modifications\n• File manager for browsing and editing system files\n• ADB sideload for installing packages\n• Terminal access for advanced operations\n• Partition management and formatting\n\nWHY USE THIS IMAGE\nChoose this variant when you want a clean NoGApps and NoAmazon WSA environment without root. Users requiring Google Apps should choose a GApps variant, while users requiring root should choose a Magisk variant."
}
```

**Inject**
```powershell
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps-NoAmazon.img"
```

**Verify**
```powershell
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps-NoAmazon.img"
```

---

### Injection order for all 7

```powershell
# Step 1: Copy each JSON to C:\Users\C Y B E R B U D D Y\Documents\info.json
# Step 2: Run inject for each image
# Step 3: Run status to verify TWRP Support: True

# --- Variant 1: GApps Standard ---
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0.img"
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0.img"

# --- Variant 2: GApps + NoAmazon ---
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0-NoAmazon.img"
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-GApps-13.0-NoAmazon.img"

# --- Variant 3: Magisk Stable + GApps ---
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-GApps-13.0.img"
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-GApps-13.0.img"

# --- Variant 4: NoGApps ---
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps.img"
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps.img"

# --- Variant 5: Magisk Canary + GApps + NoAmazon ---
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-canary-GApps-13.0-NoAmazon.img"
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-canary-GApps-13.0-NoAmazon.img"

# --- Variant 6: Magisk Stable + NoGApps + NoAmazon ---
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-NoGApps-NoAmazon.img"
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-with-magisk-30.6.30600.-stable-NoGApps-NoAmazon.img"

# --- Variant 7: NoGApps + NoAmazon ---
venv\Scripts\python.exe twrp.py --inject-file "C:\Users\C Y B E R B U D D Y\Documents\info.json" --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps-NoAmazon.img"
venv\Scripts\python.exe twrp.py --status --path "C:\Users\C Y B E R B U D D Y\Downloads\initrd\initrd_WSA_2407.40000.4.0_x64_Release-Nightly-NoGApps-NoAmazon.img"
```
