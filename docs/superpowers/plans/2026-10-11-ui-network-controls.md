# Desktop sizing and network controls

User-approved scope: independent QR and text-area sizing, automatic LAN-first connection by default, and an optional LAN-only mode.

- [x] Confirm original QR window prohibits resizing and always starts Tailcat; Android already prefers LAN.
- [x] Write and observe failing UI tests for QR resizing, independent history divider, and LAN-only pairing without remote startup.
- [x] Add a resizable pairing window, discrete QR module sizing slider, scrollable QR viewport, history divider, and text font slider.
- [x] Add persistent automatic/LAN-only selector, stop remote asynchronously, block late remote startup, and encode LAN-only QR without a remote address.
- [x] Add regression tests for preference persistence and nonblocking remote shutdown during startup.
- [x] Run full Python suite: 80 tests, one skipped, zero failures. Existing ignored Android pairing asset temporarily backed up outside repository and restored for publication tests.
- [x] Review changes; fix blocking shutdown identified by reviewer; follow-up review reports no blockers.
- [x] Build final Windows candidate, verify first-run visibility and HTTPS receiver lifecycle, inspect QR and main layouts, verify archive equality and no private configuration.

Changing the connection mode requires re-scanning so the existing Android APK saves the corresponding pairing transport. No Android code changes or new APK are needed. No phone-to-computer or remote-network end-to-end acceptance is claimed.
