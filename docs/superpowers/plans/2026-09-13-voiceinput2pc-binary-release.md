# VoiceInput2PC v0.3.0 Downloadable Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a public `v0.3.0` GitHub preview release containing a generic Android APK and Windows portable ZIP that pair on first use and contain no personal credentials.

**Architecture:** The Windows receiver owns credential generation and serializes a versioned pairing URI into a QR code. The generic Android app imports that URI from an intent or pasted text, validates and health-checks it, then stores it privately. Existing HTTPS certificate pinning, session arming, Unicode input, deduplication, and safety behavior remain unchanged.

**Tech Stack:** Python 3.13, Tkinter, `cryptography`, `qrcode`, PyInstaller, Java/Android API 26+, Gradle 8.10.2, Android SDK 35, GitHub CLI.

---

## File structure

- Create `receiver/pairing.py`: pure pairing format, validation, certificate/config generation, address detection.
- Create `receiver/first_run.py`: first-run and re-pair Tkinter UI, in-memory QR rendering, autostart setting.
- Modify `receiver_app.py`: enter setup when config is absent and expose “配对手机”.
- Modify `scripts/provision.py`: thin CLI over the shared pairing module.
- Create `android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingConfig.java`: immutable validated configuration.
- Create `android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingCodec.java`: custom-URI codec with no Android dependency.
- Create `android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingStore.java`: Android-private persistence.
- Modify `MainActivity.java`, `RelayClient.java`, and `AndroidManifest.xml`: first-run pairing, intent import, paste fallback, health verification.
- Create `tests/test_pairing.py` and `tests/PairingCodecTest.java`: cross-language pairing vectors and invalid-input coverage.
- Create `tests/test_first_run.py`: provisioning, address selection, and no-secret-output coverage.
- Modify `requirements.txt` and `VoiceInput2PCReceiver.spec`: include QR support in the receiver executable.
- Create `scripts/build_public_release.ps1`: clean, signed, privacy-scanned APK/ZIP/checksum assembly.
- Create `release/使用说明.txt`: four-step packaged quick start.
- Modify `README.md` and `SECURITY.md`: download-first documentation and pairing-QR security.

### Task 1: Define one cross-platform pairing format

**Files:**
- Create: `tests/test_pairing.py`
- Create: `receiver/pairing.py`

- [ ] **Step 1: Write the failing Python pairing tests**

```python
import unittest
from receiver.pairing import Pairing, decode_pairing, encode_pairing


class PairingTests(unittest.TestCase):
    def test_known_vector_round_trips_without_secret_output(self):
        value = Pairing('192.168.1.20', 23337, 'A' * 43, 'ab' * 32)
        uri = encode_pairing(value)
        self.assertTrue(uri.startswith('voiceinput2pc://pair?p='))
        self.assertEqual(value, decode_pairing(uri))
        self.assertNotIn(value.token, repr(value))

    def test_invalid_pairing_is_rejected(self):
        for raw in ('', 'https://example.com', 'voiceinput2pc://pair?p=bad'):
            with self.assertRaises(ValueError):
                decode_pairing(raw)
```

- [ ] **Step 2: Run the new test and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_pairing -v`

Expected: FAIL because `receiver.pairing` does not exist.

- [ ] **Step 3: Implement the minimal immutable codec**

Use a URL-safe Base64 payload containing five UTF-8 lines in this exact order: version `1`, host, decimal port, token, lowercase certificate fingerprint. Reject input over 4096 characters, hosts outside `[A-Za-z0-9.-]+`, ports outside `1..65535`, tokens outside `[A-Za-z0-9_-]{32,128}`, and fingerprints outside `[0-9a-f]{64}`. `Pairing.__repr__` must redact the token and fingerprint.

```python
@dataclass(frozen=True)
class Pairing:
    host: str
    port: int
    token: str = field(repr=False)
    fingerprint: str = field(repr=False)

def encode_pairing(value: Pairing) -> str:
    validate_pairing(value)
    raw = f'1\n{value.host}\n{value.port}\n{value.token}\n{value.fingerprint}'.encode()
    payload = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    return 'voiceinput2pc://pair?p=' + payload
```

- [ ] **Step 4: Run the targeted and full Python suites**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_pairing -v`

Expected: 2 tests PASS.

Run: `\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all existing and new tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add receiver/pairing.py tests/test_pairing.py
git commit -m "feat: define secure pairing payload"
```

### Task 2: Share safe first-run provisioning with the packaged receiver

**Files:**
- Create: `tests/test_first_run.py`
- Modify: `receiver/pairing.py`
- Modify: `scripts/provision.py`

- [ ] **Step 1: Write failing provisioning tests**

Test a temporary directory and assert that `prepare_receiver(folder, host, 23337)` creates `config.json`, `cert.pem`, and `key.pem`; returns a `Pairing`; writes no secret to stdout/stderr; uses atomic replacement; and reuses an existing valid configuration unless `regenerate=True`. Test `detect_private_addresses()` with injected address candidates so loopback, link-local, duplicates, and public addresses are excluded.

```python
with tempfile.TemporaryDirectory() as folder:
    pairing = prepare_receiver(Path(folder), '192.168.1.20', 23337)
    self.assertEqual('192.168.1.20', pairing.host)
    self.assertTrue((Path(folder) / 'config.json').is_file())
    self.assertTrue((Path(folder) / 'cert.pem').is_file())
    self.assertTrue((Path(folder) / 'key.pem').is_file())
```

- [ ] **Step 2: Run and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_first_run -v`

Expected: FAIL because `prepare_receiver` and injectable address selection do not exist.

- [ ] **Step 3: Move credential generation into `receiver/pairing.py`**

Reuse the existing RSA-2048 and X.509 logic from `scripts/provision.py`. Write each new file to the target directory with a unique `.tmp` suffix, flush and close it, then replace its final path. Preserve a complete existing configuration when any generation step fails. Return only the redacted `Pairing` object.

- [ ] **Step 4: Make `scripts/provision.py` a CLI wrapper**

The CLI validates arguments, calls `prepare_receiver`, writes the ignored Android asset only when `--asset` is explicitly supplied, and prints only `Local pairing prepared; credentials were not printed.`. Importing the module must have no filesystem side effect.

- [ ] **Step 5: Run provisioning and regression tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_first_run tests.test_provision tests.test_pairing -v`

Expected: all targeted tests PASS.

Run: `\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: full suite PASS.

- [ ] **Step 6: Commit**

```powershell
git add receiver/pairing.py scripts/provision.py tests/test_first_run.py tests/test_provision.py
git commit -m "feat: provision receiver on first run"
```

### Task 3: Add Windows setup and pairing UI

**Files:**
- Create: `receiver/first_run.py`
- Modify: `receiver_app.py`
- Modify: `requirements.txt`
- Modify: `VoiceInput2PCReceiver.spec`
- Test: `tests/test_first_run.py`

- [ ] **Step 1: Add failing pure tests for UI decisions**

Test `choose_default_address`, `autostart_command`, and `pairing_view_model` without opening Tkinter. Assert that private Ethernet/Wi-Fi addresses outrank Tailscale and that the command quotes paths containing spaces.

```python
self.assertEqual('192.168.1.20', choose_default_address(['100.64.0.2', '192.168.1.20']))
self.assertEqual('"C:\\Program Files\\VoiceInput2PCReceiver.exe"', autostart_command(Path(r'C:\Program Files\VoiceInput2PCReceiver.exe')))
```

- [ ] **Step 2: Run and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_first_run -v`

Expected: FAIL for the new missing functions.

- [ ] **Step 3: Implement `receiver/first_run.py`**

Provide:

```python
def run_first_setup(root, folder: Path, executable: Path) -> bool:
    return FirstRunDialog(root, folder, executable).run()

def show_pairing(root, pairing: Pairing, allow_regenerate: bool) -> None:
    PairingDialog(root, pairing, allow_regenerate).show_modal()

def set_autostart(enabled: bool, executable: Path) -> None:
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        if enabled:
            winreg.SetValueEx(key, 'VoiceInput2PC', 0, winreg.REG_SZ,
                              autostart_command(executable))
        else:
            try:
                winreg.DeleteValue(key, 'VoiceInput2PC')
            except FileNotFoundError:
                pass
```

Use `qrcode.QRCode` to render `encode_pairing(pairing)` directly to a Pillow image and then to `ImageTk.PhotoImage`; never save it. The setup dialog validates the address, provisions into `%LOCALAPPDATA%\VoiceInput2PC`, optionally writes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\VoiceInput2PC`, and returns only after configuration is complete.

- [ ] **Step 4: Integrate setup and re-pairing into `receiver_app.py`**

Create the hidden Tk root before loading config. If config is missing, call `run_first_setup`; cancellation exits cleanly. Add a `配对手机` button to the normal status window. Regeneration requires a confirmation dialog, pauses input first, atomically replaces credentials, and restarts the local HTTPS server before showing the new QR.

- [ ] **Step 5: Pin and package QR dependencies**

Add `qrcode[pil]>=8,<9` to `requirements.txt`. Update the PyInstaller spec so `qrcode` and required image modules are collected in the one-file executable.

- [ ] **Step 6: Run tests and a temporary first-run smoke check**

Run: `\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: full suite PASS.

Run the built receiver with `--config-dir` pointing at a new temporary directory and `--show`; confirm the setup window appears and no personal configuration is read.

- [ ] **Step 7: Commit**

```powershell
git add receiver/first_run.py receiver_app.py requirements.txt VoiceInput2PCReceiver.spec tests/test_first_run.py
git commit -m "feat: add Windows QR pairing setup"
```

### Task 4: Implement the Android pairing model and codec

**Files:**
- Create: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingConfig.java`
- Create: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingCodec.java`
- Create: `tests/PairingCodecTest.java`

- [ ] **Step 1: Write the failing plain-JDK test**

Use the same known vector as Python. Cover valid round-trip, missing padding restoration, wrong scheme, wrong version, control characters, invalid host/port/token/fingerprint, and an oversized input. Assert `PairingConfig.toString()` does not reveal token or fingerprint.

```java
PairingConfig config = new PairingConfig("192.168.1.20", 23337, "A".repeat(43), "ab".repeat(32));
String uri = PairingCodec.encode(config);
check(PairingCodec.decode(uri).equals(config));
check(!config.toString().contains(config.token));
```

- [ ] **Step 2: Run and verify RED**

Compile with JDK 17 against the new test and verify failure because the pairing classes are absent.

- [ ] **Step 3: Implement the two dependency-free Java classes**

Use `java.util.Base64.getUrlEncoder().withoutPadding()` and `getUrlDecoder()`. Enforce the exact format and validation limits defined in Task 1. Use constant field names `host`, `port`, `token`, and `fingerprint`, and redact secrets from `toString()`.

- [ ] **Step 4: Run Java tests**

Compile `PairingConfig.java`, `PairingCodec.java`, and `PairingCodecTest.java`, then run `io.github.amxooo.voiceinput2pc.PairingCodecTest`.

Expected: all pairing checks PASS. Re-run the existing `CommitTrackerTest` and `DraftLogicTest`; 42 and 6 checks PASS.

- [ ] **Step 5: Commit**

```powershell
git add android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingConfig.java android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingCodec.java tests/PairingCodecTest.java
git commit -m "feat: add Android pairing codec"
```

### Task 5: Add Android first-run import and verification

**Files:**
- Create: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/PairingStore.java`
- Modify: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/MainActivity.java`
- Modify: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/RelayClient.java`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Modify: `android/app/src/androidTest/java/io/github/amxooo/voiceinput2pc/MainActivityTest.java`

- [ ] **Step 1: Write failing Android tests**

Add tests that launch with empty preferences and observe the pairing screen; send the exact URI returned by `PairingCodec.encode(testConfig)` through `ACTION_VIEW`; verify a malformed payload does not replace stored configuration; verify a valid payload is health-checked before persistence; and verify pasted content follows the same path.

- [ ] **Step 2: Run the available compile/test target and verify RED**

Run the Android test compilation task. Expected: compilation or assertions fail because the pairing store and screen do not exist.

- [ ] **Step 3: Implement private persistence and RelayClient construction**

`PairingStore` stores the four validated fields in the existing private SharedPreferences file and returns `null` when incomplete. `RelayClient` accepts `PairingConfig` instead of an asset `JSONObject`. Remove all runtime dependency on `assets/pairing.json`.

- [ ] **Step 4: Implement the first-run screen**

When no pairing exists, show a concise screen with title `连接电脑`, instructions to scan the Windows QR, a multiline paste field, and `导入并连接`. Process `ACTION_VIEW` in both `onCreate` and `onNewIntent`. Validate, health-check on the worker thread, then persist and enter the existing typing UI. While checking, disable the import button and show a clear progress message.

- [ ] **Step 5: Preserve an existing pairing on failure**

Keep candidate configuration in memory until HTTPS pinning, bearer authentication, application name `VoiceInput2PC`, and protocol `2` all pass. Any failure displays a specific message and leaves the prior `PairingStore` values untouched.

- [ ] **Step 6: Add the custom URI intent filter**

Declare an exported launcher activity with a separate `VIEW` intent filter for scheme `voiceinput2pc` and host `pair`. Keep the manifest permission list to `android.permission.INTERNET` only.

- [ ] **Step 7: Run Android and regression tests**

Run `assembleDebug`, Android test compilation, plain-Java tests, and the Python suite. Inspect the merged manifest and APK permissions; camera and microphone permissions must be absent.

- [ ] **Step 8: Commit**

```powershell
git add android/app/src/main android/app/src/androidTest
git commit -m "feat: pair generic Android app on first use"
```

### Task 6: Build signed public artifacts without secrets

**Files:**
- Modify: `android/app/build.gradle`
- Create: `scripts/build_public_release.ps1`
- Create: `release/使用说明.txt`
- Modify: `.gitignore`
- Test: `tests/test_publication.py`

- [ ] **Step 1: Add failing publication tests**

Assert that the public APK build has no required `pairing.json`, release output paths are ignored, public asset names are exact, and the build script refuses to run without all four signing environment variables.

- [ ] **Step 2: Run and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_publication -v`

Expected: FAIL for the missing release build behavior.

- [ ] **Step 3: Configure release signing only from the environment**

Read `VOICEINPUT2PC_KEYSTORE`, `VOICEINPUT2PC_STORE_PASSWORD`, `VOICEINPUT2PC_KEY_ALIAS`, and `VOICEINPUT2PC_KEY_PASSWORD` in `android/app/build.gradle`. Fail release configuration when any value is missing; never print them.

- [ ] **Step 4: Implement `scripts/build_public_release.ps1`**

The script verifies a clean Git worktree, runs all tests, builds PyInstaller and Gradle release outputs, creates a temporary release directory, copies only the EXE and quick-start file into the ZIP, renames the APK, writes two SHA-256 lines, and performs a final filename/content scan. It must abort if it finds `pairing.json`, PEM headers, known personal addresses, `PocketType`, database files, logs, or extra binaries.

- [ ] **Step 5: Create and protect a dedicated Android signing key**

Generate one `VoiceInput2PC` key under `%LOCALAPPDATA%\VoiceInput2PCRelease` with a random password. Store the key and local credentials outside the repository, restrict them to the current Windows user, and record only the public certificate SHA-256 in the release verification notes.

- [ ] **Step 6: Build the exact release files**

Run `scripts\build_public_release.ps1`. Expected output directory contains only:

```text
VoiceInput2PC-Android-v0.3.0.apk
VoiceInput2PC-Windows-v0.3.0.zip
SHA256SUMS.txt
```

- [ ] **Step 7: Verify artifacts independently**

Extract the ZIP to a new temporary directory. Verify its EXE hash, first-run behavior with an empty temporary local-data directory, generated QR presence, authenticated health, and absence of private files in the ZIP. Use `aapt dump permissions` on the final APK and inspect its file table for forbidden assets.

- [ ] **Step 8: Commit**

```powershell
git add android/app/build.gradle scripts/build_public_release.ps1 release/使用说明.txt .gitignore tests/test_publication.py
git commit -m "build: produce signed public release artifacts"
```

### Task 7: Make downloads the primary documentation path

**Files:**
- Modify: `README.md`
- Modify: `SECURITY.md`
- Test: `tests/test_publication.py`

- [ ] **Step 1: Add failing documentation assertions**

Require a `下载成品` section above source-build instructions, the latest release URL, exact APK and ZIP names, QR handling, private-network firewall guidance, SmartScreen/unknown-source wording, and a warning that the QR is a password equivalent.

- [ ] **Step 2: Run and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_publication -v`

Expected: FAIL because README still says no generic binaries are available.

- [ ] **Step 3: Rewrite the README opening and security guidance**

Link `https://github.com/AMXOOO/VoiceInput2PC/releases/latest`, lead with the four user steps, retain source-build instructions below, and explain unsigned-package warnings without recommending global security disablement. Document QR regeneration after exposure.

- [ ] **Step 4: Run documentation and full tests**

Run publication tests and the full Python suite. Search tracked files for stale `源码预览版`, `暂不提供通用`, personal addresses, credentials, and wrong-owner namespace.

- [ ] **Step 5: Commit**

```powershell
git add README.md SECURITY.md tests/test_publication.py
git commit -m "docs: lead with downloadable packages"
```

### Task 8: End-to-end acceptance and GitHub Release upload

**Files:**
- No source changes expected; upload only verified files from the ignored release output directory.

- [ ] **Step 1: Run the complete verification gate on the release commit**

Run the full Python suite, all three plain-Java test programs, a clean Android release build, PyInstaller build, `git diff --check`, `git fsck --full`, tracked-history secret scan, APK permission/file scan, and ZIP content/hash scan. Record exact pass counts and commit SHA.

- [ ] **Step 2: Test exact packaged Windows executable**

With a new temporary local-data directory, complete first run, verify QR generation, local and LAN pinned HTTPS health, and receiver restart without queued text. Test Unicode insertion in Notepad, Word, Chrome, and the Codex input box; verify clipboard remains unchanged and no Enter is sent.

- [ ] **Step 3: Test Android pairing handling**

Install the exact signed APK on an available Android device or emulator. Launch the exact QR URI through `adb shell am start -a android.intent.action.VIEW -d <uri>` without printing the URI to logs, verify pairing and one text transfer, then verify malformed replacement input preserves the working pairing. If an actual phone camera scan is unavailable, keep the release marked Preview and state that boundary.

- [ ] **Step 4: Push the source commit**

Run `git push origin main`, then verify `git rev-parse HEAD` equals the GitHub `main` SHA. Do not force-push.

- [ ] **Step 5: Create and verify the public release**

Create annotated tag `v0.3.0` on the verified commit and use GitHub CLI to publish the three files as a prerelease titled `VoiceInput2PC v0.3.0｜首个可下载版本`. Release notes lead with the download/install flow and list the exact untested boundary, if any.

Run:

```powershell
gh release create v0.3.0 `
  VoiceInput2PC-Android-v0.3.0.apk `
  VoiceInput2PC-Windows-v0.3.0.zip `
  SHA256SUMS.txt `
  --repo AMXOOO/VoiceInput2PC --prerelease `
  --title 'VoiceInput2PC v0.3.0｜首个可下载版本' `
  --notes-file release-notes.md
```

- [ ] **Step 6: Verify the actual public downloads**

Use GitHub API to verify repository visibility, tag target SHA, release status, exact three asset names, sizes, and download URLs. Download all three assets into a new temporary directory, recompute SHA-256, compare against the downloaded checksum file, and confirm the downloaded APK/ZIP scans still pass.

- [ ] **Step 7: Report the release URL and acceptance boundary**

Return the clickable GitHub Release URL, artifact names, exact test counts, package permission result, and whether a physical system-camera scan was completed. State explicitly that the existing personal installation and credentials were not uploaded or modified.
