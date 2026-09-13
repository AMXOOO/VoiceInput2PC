# VoiceInput2PC v0.3.0 Downloadable Release Design

## Goal

Publish a real downloadable GitHub release for `AMXOOO/VoiceInput2PC`. A normal user must be able to download the Android APK and Windows package without compiling source code. The public artifacts must not contain the current user's address, token, certificate, private key, message database, or Android signing key.

This release remains a direct phone-to-PC tool. It does not add accounts, cloud relay, speech recognition, clipboard-based typing, or automatic Enter.

## Release artifacts

GitHub Release `v0.3.0` will contain exactly these public downloads:

- `VoiceInput2PC-Android-v0.3.0.apk`
- `VoiceInput2PC-Windows-v0.3.0.zip`
- `SHA256SUMS.txt`

The Windows archive contains the portable receiver executable and a short four-step Chinese quick-start file. GitHub source archives remain available automatically, but they are not presented as the end-user installation path.

The first binary release is marked as a preview because the binaries are not commercially code-signed. The release notes must explain the Windows SmartScreen and Android unknown-source prompts without telling users to disable system security globally.

## Separation from the existing personal installation

The currently installed personal build uses the old `PocketType` data directory and personalized APK. Development and testing of v0.3.0 must not overwrite, restart, migrate, publish, or remove that installation.

The public build uses:

- Android application ID `io.github.amxooo.voiceinput2pc`
- Windows data directory `%LOCALAPPDATA%\VoiceInput2PC`
- receiver executable name `VoiceInput2PCReceiver.exe`

Because the public Android application ID differs from the personal build, both can remain installed during acceptance testing.

## Windows first-run flow

When `%LOCALAPPDATA%\VoiceInput2PC\config.json` is absent, the receiver opens a setup window instead of showing a missing-configuration error.

The setup window:

1. Detects usable private IPv4 addresses and selects the most likely LAN address.
2. Allows the user to correct the address before pairing.
3. Generates a local TLS certificate, private key, random bearer token, certificate fingerprint, and empty message database.
4. Starts the receiver on TCP port `23337`.
5. Displays a QR code and a copyable pairing string.
6. Offers current-user automatic startup, enabled by default and implemented without administrator privileges.

The QR image and pairing string are generated in memory. They are not written to logs, diagnostics, the repository, or the release archive. The screen states that anyone who obtains the QR can connect to this receiver.

The normal receiver status window includes a “配对手机” action that shows the same pairing screen again. A “重新生成配对” action requires confirmation because it replaces the token and invalidates previously paired phones.

If no usable address is detected, setup remains usable and asks for an IPv4 address or DNS hostname. Port binding, configuration, and certificate failures produce specific Chinese errors and leave the previous valid configuration unchanged.

## Android first-run and pairing flow

The public APK contains no `pairing.json` and no shared credential. On first launch it shows a pairing screen rather than an error.

The preferred path is:

1. The user opens the Windows receiver's pairing screen.
2. The user scans the QR with the phone's existing system camera or QR scanner.
3. The scanner opens a custom URI handled by VoiceInput2PC.
4. VoiceInput2PC validates the complete payload, saves it in Android private app storage, verifies the pinned certificate and receiver health response, and only then enters the typing screen.

The URI scheme is `voiceinput2pc://pair`. Its payload contains a version, host, port, random token, and SHA-256 certificate fingerprint. All values are encoded as one URL-safe payload so scanners do not reorder or reinterpret fields.

Some Android scanners display non-HTTP QR content as text instead of opening the app. The pairing screen therefore also accepts pasting the complete pairing string. Manual entry of individual tokens or certificate fingerprints is not exposed.

Malformed, incomplete, oversized, or unsupported-version pairing data is rejected without replacing a working pairing. A newly imported valid pairing is tested before it replaces the previous one. Users may edit only the computer address later; changing security credentials requires a new pairing import.

The app does not include a camera library and requests no camera permission. Its only runtime capability remains network access. QR scanning is delegated to the user's existing scanner.

## Pairing and transport security

Pairing is an out-of-band visual transfer from the PC screen to the phone. Normal text traffic continues over certificate-pinned HTTPS with a random bearer token.

Public artifacts contain no usable token or private material. The release pipeline must scan the repository, Git history, APK, Windows archive, and checksum manifest for private file names, known personal values, key headers, and unexpected executable assets before upload.

The pairing QR is equivalent to a password. Documentation tells users not to photograph, publish, or forward it. This release does not expose the receiver through router port forwarding and does not introduce a public relay. LAN is the documented default; a user may later enter a stable Tailscale address, but Tailscale automation is out of scope.

## Packaging and signing

The Android APK is signed with a dedicated VoiceInput2PC release key stored outside the repository. The key and passwords are never written to Git, build logs, release notes, or release assets. The same key must be retained for future APK updates.

The Windows executable is produced with PyInstaller from a clean checkout. QR generation dependencies are pinned in `requirements.txt` and included in the executable. The ZIP contains no configuration directory, credentials, database, build cache, or private diagnostics.

Build artifacts are assembled in a temporary release directory with deterministic public names. `SHA256SUMS.txt` records SHA-256 for the APK and ZIP only.

## Documentation changes

The README's opening section changes from “源码预览版” to a prominent download section linking to the latest GitHub Release. Building from source remains documented below the normal installation instructions.

The quick start for end users is:

1. Download and extract the Windows ZIP, then run the receiver.
2. Allow access on Windows private networks if Windows asks.
3. Install the APK and scan the receiver's pairing QR once.
4. Click a Windows input position, tap Start on the phone, and use the phone input method's voice button.

## Error handling and recovery

- Missing Windows configuration enters setup; it is not treated as a fatal installation error.
- An occupied port identifies port `23337` and does not silently change the port after a QR has been issued.
- A failed pairing test leaves any previous Android pairing active.
- A changed PC address can be edited without regenerating credentials.
- A lost or exposed QR is recovered by regenerating pairing on the PC and pairing phones again.
- Receiver restart and Windows automatic startup never type queued text; the user must explicitly arm a fresh target session.

## Verification and release gate

No GitHub release is created until all checks below pass on the exact release commit and exact uploaded files:

- Existing Python and plain-Java regression suites pass.
- New unit tests cover Windows first-run provisioning, pairing serialization and validation, malformed input, and preservation of a previous valid pairing.
- Android tests cover first launch without embedded credentials, custom-URI import, paste fallback, and successful health verification.
- A clean checkout builds the Windows executable and release-signed Android APK.
- The APK manifest contains network access but no camera or microphone permission.
- The APK does not contain `pairing.json`, a real token, a personal address, or a private key.
- The Windows ZIP starts with an empty temporary `LOCALAPPDATA`, generates its own configuration, displays pairing, and passes local authenticated health checks.
- The packaged receiver is tested in Notepad, Word, Chrome, and the Codex input box without changing the clipboard or automatically pressing Enter.
- Local commit, remote `main`, release tag, and release asset hashes match.
- The GitHub release is publicly visible and its three expected assets download successfully.

If a physical phone is unavailable for the final system-camera scan, `v0.3.0` remains marked Preview and the unverified camera-to-custom-URI step is stated explicitly. Simulating the URI with Android tooling verifies application handling but does not count as a real camera acceptance test.
