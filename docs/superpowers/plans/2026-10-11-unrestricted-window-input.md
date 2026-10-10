# Unrestricted window input implementation plan

**Goal:** Attempt text input into any focused window without an application-name, process-access, elevation, or desktop-name preflight veto.

**Architecture:** Capture the foreground window and focus handles directly. Let SendInput report acceptance; preserve target-change detection and avoid replay after partial insertion. System access boundaries remain enforced by Windows.

**Tech stack:** Python, ctypes, Win32, unittest, PyInstaller.

- [x] Add capture regression tests with inaccessible process metadata, elevated tokens, terminal executables, and receiver-owned windows; run them against the old code and confirm rejection.
- [x] Remove process and desktop policy gates and unused Win32 declarations from receiver/win_input.py. Add Win32 error details to actual SendInput failures without claiming that every failure is elevation-related.
- [x] Run input regression tests and the full Python test suite.
- [x] Build a separately named Windows candidate and verify its first-run and receiver runtime checks. Do not publish or replace an existing running receiver automatically.

Earlier independent QR/text resizing requirements remain pending and are not implemented by this permission change.

Validation: 74 Python tests passed, one skipped. Local preexisting Android pairing asset was temporarily backed up outside the repository for publication tests and restored in finally. HTTP tests initially encountered intermittent Windows 10053; isolated rerun and final full suite passed. Packaged first-run UI and receiver HTTPS runtime checks passed. No phone/terminal/elevated-window end-to-end acceptance is claimed.
