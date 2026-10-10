# Mobile usability and route diagnostics

User-authorized changes: fix the keyboard shrinking the editor, reduce oversized controls, add an internal QR scanner, default to automatic LAN-first with remote backup, and omit the unusable experimental Bluetooth feature. The phone uses a bypass router with a modified gateway; no VPN diagnosis is assumed.

Implementation:
- Use one system-bar/IME inset calculation with edge-to-edge on API 30+, legacy adjustResize below.
- Keep the existing new/start/receive order at 48dp; move file sending, pairing scan, connection selection, diagnostics and help into More.
- Integrate JourneyApps ZXing QR scanning, request camera only on launch, keep fingerprint/token validation before saving a pairing, handle Activity recreation on camera return.
- Add persisted per-computer automatic/LAN-only preference, immediate re-probe, and sanitized LAN failure diagnostics; bypass HTTP proxy for HTTPS requests.
- Preserve a proven LAN endpoint when authenticated health advertises multiple NICs. Do not infer that a router gateway can be bypassed in application code.
- Base the candidate on v0.6 testing without PR6 experimental HID: it lacks generic Chinese Windows input and needs editor-specific workarounds. Physical Bluetooth failure remains unconfirmed.
- Exclude private pairing assets in Gradle. Build a separate candidate application so the installed app is preserved, and obtain the complete native remote bridge from CI.

Validation: failing baseline scanner/control tests reproduced first; the initial modified Activity passed 19 existing tests. Add keyboard geometry, scan return after recreation and deterministic LAN-first/fallback tests. Review found a scanner-result null dereference after recreation, corrected before final verification. Final status recorded after builds/tests finish.
