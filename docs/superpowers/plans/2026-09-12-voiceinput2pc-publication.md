# VoiceInput2PC Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the working personal prototype into a clean source-only public repository named `AMXOOO/VoiceInput2PC` without publishing any personal pairing material or binaries.

**Architecture:** Keep the existing Android-to-Windows text transport and safety behavior. Rename public and internal project identifiers for a clean independent identity, make credential provisioning require an explicit target address, then publish only reviewed source and documentation. The currently installed personal APK/receiver and workspace `outputs/` remain untouched.

**Tech Stack:** Python 3.13, unittest, Win32 ctypes/Tk/pystray, Java 8 source level, Android SDK 35, Gradle 8.10.2, Git, GitHub.

---

### Task 1: Lock the public identity

**Files:**
- Create: `tests/test_publication.py`
- Modify: `android/app/build.gradle`
- Modify: `android/settings.gradle`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Modify: `android/app/src/main/java/local/pockettype/*.java`
- Modify: `android/app/src/androidTest/java/local/pockettype/*.java`
- Modify: `tests/*.java`
- Modify: `receiver_app.py`
- Modify: `receiver/http_server.py`
- Modify: `receiver/win_input.py`
- Rename: `PocketTypeReceiver.spec` to `VoiceInput2PCReceiver.spec`
- Modify: `scripts/update_receiver.ps1`

- [ ] **Step 1: Write the failing identity test**

Add assertions that the Android application ID is `io.github.amxooo.voiceinput2pc`, the visible Android label is `语音输入电脑`, the server health name is `VoiceInput2PC`, the default data directory is `VoiceInput2PC`, and visible source files no longer present “随手输入”.

- [ ] **Step 2: Run the identity test and confirm RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_publication -v`

Expected: FAIL because the source still uses PocketType and 随手输入 identifiers.

- [ ] **Step 3: Apply the identity rename**

Rename package declarations to `io.github.amxooo.voiceinput2pc`, public labels to `VoiceInput2PC｜手机语音输入电脑` or the compact platform label, receiver identifiers and default local data folder to `VoiceInput2PC`, and build output to `VoiceInput2PCReceiver.exe`. Keep protocol version `2` and behavior unchanged.

- [ ] **Step 4: Run the identity test and existing suites**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all Python tests pass.

Run the existing Java state-machine tests with the renamed package and expect every check to pass.

- [ ] **Step 5: Commit the identity change**

Commit message: `refactor: rename project to VoiceInput2PC`

### Task 2: Make provisioning safe for public source

**Files:**
- Create: `tests/test_provision.py`
- Modify: `scripts/provision.py`
- Create: `android/app/src/main/assets/pairing.example.json`

- [ ] **Step 1: Write failing provisioning tests**

Test that importing `scripts.provision` has no side effects, a new configuration requires an explicit `--host`, IPv4 and DNS hostnames are validated, generated credentials are written only to caller-selected temporary paths, and console output never includes the token or fingerprint.

- [ ] **Step 2: Run the provisioning tests and confirm RED**

Run: `.venv\Scripts\python.exe -m unittest tests.test_provision -v`

Expected: FAIL because the current script executes on import and hard-codes a personal LAN address.

- [ ] **Step 3: Implement generic provisioning**

Move execution behind `main()`, accept `--host`, `--port`, `--config-dir`, and `--asset` arguments, require `--host` when no existing configuration exists, support an IPv4 address or DNS hostname in the certificate SAN, reuse existing credentials without printing them, and write a placeholder-only example asset.

- [ ] **Step 4: Run provisioning and regression tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_provision -v`

Expected: all provisioning tests pass.

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all Python tests pass.

- [ ] **Step 5: Commit provisioning**

Commit message: `feat: add safe local pairing setup`

### Task 3: Add public-facing documentation and repository policy

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `SECURITY.md`
- Modify: `.gitignore`
- Modify: `requirements.txt`

- [ ] **Step 1: Extend the publication test and confirm RED**

Require the four public metadata files, an MIT license, a Chinese-first description of the exact data flow, explicit source-only status, supported Windows/Android versions, build steps, no-microphone/no-clipboard/no-auto-Enter statements, security limits, and the personal-build exclusion.

- [ ] **Step 2: Write the public files**

Write concise Chinese-first documentation, an MIT license for 2026 AMXOOO, private vulnerability reporting guidance, complete ignore rules for credentials/build/cache/log/database/signing artifacts, and pinned Python dependencies already used by the project.

- [ ] **Step 3: Run documentation tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_publication -v`

Expected: all publication tests pass.

- [ ] **Step 4: Commit documentation**

Commit message: `docs: prepare public source repository`

### Task 4: Verify, publish, and inspect GitHub

**Files:**
- Review all tracked files.
- Do not add `outputs/`, real pairing assets, build products, logs, databases, keys, or certificates.

- [ ] **Step 1: Run clean verification**

Run the full Python tests, pure Java tests, and offline Android release build using a temporary generated pairing asset. Confirm the APK requests INTERNET only and does not request microphone access.

- [ ] **Step 2: Review the staged tree and scan for secrets**

List every tracked path. Scan tracked content for private-key headers, bearer tokens, high-entropy pairing values, personal LAN addresses, local user paths, APK/EXE/database/log files, and signing material. Any match must be explained as a harmless placeholder/test fixture or removed before push.

- [ ] **Step 3: Commit the verified public tree**

Commit message: `chore: prepare initial public source release`

- [ ] **Step 4: Create and push the public repository**

Create `AMXOOO/VoiceInput2PC` as a public repository with description `用安卓手机输入法，把语音识别文字直接输入 Windows 当前光标位置。`, add it as `origin`, and push `main`. Authentication may require the account owner to complete GitHub sign-in.

- [ ] **Step 5: Verify the public result**

Open the public repository, verify its owner/name/visibility/default branch/README and tracked file list, and confirm no GitHub Release or personal binary was created.
