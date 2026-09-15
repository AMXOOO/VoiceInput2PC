# PC-to-Phone Text Receive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal, authenticated PC-to-phone text path with one Windows clipboard action and one Android receive button.

**Architecture:** Extend the existing SQLite-backed `Relay` with a durable single-slot phone outbox, expose authenticated HTTPS peek/ack endpoints, and let Android fetch only on a button press. Applying received text resets the existing tracker while paused so the programmatic change cannot echo to the PC.

**Tech Stack:** Python 3 `unittest`, SQLite, `ThreadingHTTPServer`, Tkinter, Android Java, `HttpsURLConnection`, Gradle instrumentation tests.

---

### Task 1: Durable phone outbox

**Files:**
- Modify: `tests/test_receiver.py`
- Modify: `receiver/core.py`

- [ ] Add failing tests proving queue/peek/ack persistence, latest-item replacement, idempotent acknowledgement, stale acknowledgement safety, and text validation.
- [ ] Run `..\..\.venv\Scripts\python.exe -m unittest tests.test_receiver -v` and confirm failures are caused by the missing outbox API.
- [ ] Implement `queue_for_phone(text)`, `phone_outbox()` and `ack_phone_outbox(id)` using one SQLite row and the existing lock.
- [ ] Re-run the receiver tests and confirm they pass.

### Task 2: Authenticated HTTPS endpoints

**Files:**
- Modify: `tests/test_http.py`
- Modify: `receiver/http_server.py`

- [ ] Add failing live-HTTP tests for authenticated `GET /outbox`, empty state, `POST /outbox/ack`, bad authorization, bad identifiers and repeat acknowledgement.
- [ ] Run `..\..\.venv\Scripts\python.exe -m unittest tests.test_http -v` and confirm the new endpoint assertions fail.
- [ ] Route the two endpoints to the Relay without logging text or credentials.
- [ ] Re-run HTTP and full Python tests.

### Task 3: Explicit Windows clipboard action

**Files:**
- Modify: `tests/test_startup.py`
- Modify: `receiver_app.py`

- [ ] Add failing unit tests for a helper that accepts a clipboard reader and never changes the outbox on empty, non-text, invalid, or oversized content.
- [ ] Implement the helper and add “发送剪贴板到手机” to the existing button row.
- [ ] On success show that the text is waiting for the phone; on failure show a concise local status without exposing content.
- [ ] Keep the existing “复制选中文字” behavior unchanged and re-run Python tests.

### Task 4: Android receive transport and UI

**Files:**
- Modify: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/RelayTransport.java`
- Modify: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/RelayClient.java`
- Modify: `android/app/src/main/java/io/github/amxooo/voiceinput2pc/MainActivity.java`
- Modify: `android/app/src/androidTest/java/io/github/amxooo/voiceinput2pc/MainActivityTest.java`

- [ ] Add instrumentation assertions for the exact `[新一段][开始输入到电脑][接收]` order.
- [ ] Add a failing test where tapping receive pauses an active session, fetches PC text, replaces the existing editor, persists it, acknowledges its id, and makes no `/text` request.
- [ ] Add failing tests for empty and malformed receive responses preserving the old draft.
- [ ] Extend the transport with `receive(host)` and `acknowledge(host,id)` using `/outbox` and `/outbox/ack`.
- [ ] Add the rightmost button and implement the single-worker receive flow with `loading`, tracker reset and durable save before acknowledgement.
- [ ] Compile and run instrumentation tests on the dedicated emulator.

### Task 5: Version, documentation and candidate packages

**Files:**
- Modify: `android/app/build.gradle`
- Modify: `receiver_app.py`
- Modify: `README.md`
- Modify: `SECURITY.md`
- Modify: `release/使用说明.txt`
- Modify: publication tests as required by the established release checks

- [ ] Bump both apps to `0.4.0` and document the exact two-step reverse flow: copy on PC, receive on phone.
- [ ] Run all Python, standalone Java and Android instrumentation tests.
- [ ] Build the signed Android candidate and Windows ZIP using the existing clean release script without printing secrets.
- [ ] Inspect APK permissions/signature, archive contents and generated SHA-256 checksums; scan outputs for private pairing material.
- [ ] Perform an end-to-end emulator/temporary-receiver test covering queue, fetch, display, pause and acknowledgement before reporting completion.
