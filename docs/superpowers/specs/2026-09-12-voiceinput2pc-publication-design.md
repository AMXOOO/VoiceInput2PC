# VoiceInput2PC Public Publication Design

## Goal

Publish the project as `AMXOOO/VoiceInput2PC` with the Chinese name “手机语音输入电脑”. The repository should make the function obvious: use an Android phone's existing input method for speech recognition, then type the confirmed text at the current Windows caret.

## Product identity

- Repository: `VoiceInput2PC`
- Public title: `VoiceInput2PC｜手机语音输入电脑`
- Android display name: `语音输入电脑`
- Windows display name: `VoiceInput2PC 接收端`
- One-line description: `用安卓手机输入法，把语音识别文字直接输入 Windows 当前光标位置。`
- This is an independent project, not a ToMic fork. ToMic transports audio; VoiceInput2PC transports confirmed text.

## First public release scope

The first publication is source-only. It includes the Windows receiver source, Android source, build and provisioning scripts, automated tests, documentation, an example pairing file, and an MIT license.

The existing personal APK and EXE are not public release artifacts. A downloadable binary release waits for a generic pairing experience so no personal credential can be embedded in a public APK.

## Security boundary

The public repository must not contain:

- the real `pairing.json`, bearer token, private key, certificate, or certificate fingerprint;
- personal APK/EXE outputs, local configuration, message database, user text, logs, caches, or build directories;
- a fixed private LAN address presented as a usable default;
- signing keys or passwords.

Provisioning must generate credentials locally without printing secrets. A tracked example configuration may contain placeholders only. A clean staged-file scan must run before every push.

## Repository contents

- `README.md`: Chinese-first overview, exact data flow, supported environment, quick start from source, limitations, privacy, and troubleshooting.
- `LICENSE`: MIT.
- `SECURITY.md`: private reporting guidance and a warning not to publish pairing information.
- `android/`: native Android application source, excluding generated pairing assets and build output.
- `receiver/` and `receiver_app.py`: Windows receiver source.
- `scripts/`: generic local provisioning, verification, and packaging helpers.
- `tests/`: unit and integration tests that do not contain user data.
- `docs/`: architecture and safety notes useful to contributors; local implementation logs and personal acceptance records remain excluded.

## Compatibility and naming migration

The currently installed personal version remains untouched while the public repository is prepared. Public-facing names change to VoiceInput2PC. Internal protocol compatibility may retain legacy identifiers where changing them would break the working personal installation; any retained identifier must be documented and must not expose private data.

## Verification before publication

1. Build and run all existing Python and Java/Android tests from the cleaned source tree.
2. Verify that the Android manifest requests no microphone permission and that text transport remains authenticated and certificate-pinned.
3. Inspect every staged path and scan staged content for credentials, private keys, local addresses, user text, binaries, logs, and generated files.
4. Confirm a fresh checkout contains enough instructions to provision and build without relying on the author's private files.
5. Create the public GitHub repository only after the clean commit is ready, then push the default branch and verify the rendered README and public file list.

## Deferred work

- QR-code pairing and a general-user installer.
- Public APK and Windows binary releases with checksums.
- Tailscale or Internet setup automation.
- Input-flow and interface optimizations discussed separately.

These items are not required for the first source publication.
