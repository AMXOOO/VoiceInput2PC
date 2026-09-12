package io.github.amxooo.voiceinput2pc;

import java.lang.reflect.*;
import java.util.Objects;

/** Plain JDK executable tests; no Android runtime or external test dependencies. */
public final class CommitTrackerTest {
    private static int checks;
    private static Class<?> trackerClass;
    private static Class<?> pendingClass;

    private static Object tracker(String sent, String draft, Object pending, boolean saved) throws Exception {
        return trackerClass.getConstructor(String.class, String.class, pendingClass, boolean.class)
            .newInstance(sent, draft, pending, saved);
    }
    private static Object empty() throws Exception { return tracker("", "", null, false); }
    private static Object call(Object target, String method, Object... args) throws Exception {
        for (Method candidate : target.getClass().getMethods()) {
            if (candidate.getName().equals(method) && candidate.getParameterCount() == args.length) {
                try { return candidate.invoke(target, args); }
                catch (InvocationTargetException e) { throw new AssertionError(method + " threw", e.getCause()); }
            }
        }
        throw new AssertionError("Missing behavior: " + method);
    }
    private static Object field(Object target, String name) throws Exception {
        return target.getClass().getField(name).get(target);
    }
    private static void equal(Object expected, Object actual, String label) {
        checks++;
        if (!Objects.equals(expected, actual)) throw new AssertionError(label + ": expected " + expected + ", got " + actual);
    }
    private static void observe(Object tracker, String text, boolean composing, boolean batch) throws Exception {
        call(tracker, "observe", text, composing, batch);
    }
    private static Object prepared(Object tracker, String text, String id) throws Exception {
        call(tracker, "start", "session-A");
        observe(tracker, text, false, false);
        return call(tracker, "prepare", id);
    }

    private static void compositionOnlyEmitsFinalCommit() throws Exception {
        Object tracker = empty();
        call(tracker, "start", "session-A");
        observe(tracker, "zhong", true, false);
        equal(null, call(tracker, "prepare", "id-1"), "composing phonetics are withheld");
        observe(tracker, "中国", true, false);
        equal(null, call(tracker, "prepare", "id-1"), "candidate revisions are withheld");
        observe(tracker, "中国", false, false);
        Object pending = call(tracker, "prepare", "id-1");
        equal("中国", field(pending, "text"), "only committed candidate is emitted");
        equal("session-A", field(pending, "session"), "pending binds captured session");
    }
    private static void batchesAndRapidRevisionCoalesce() throws Exception {
        Object tracker = empty();
        call(tracker, "start", "session-A");
        observe(tracker, "中", false, true);
        equal(null, call(tracker, "prepare", "b1"), "batch interim withheld");
        observe(tracker, "中文", false, true);
        observe(tracker, "中文完成", false, false);
        equal("中文完成", field(call(tracker, "prepare", "b1"), "text"), "completed batch emitted once");
        Object revision = empty();
        call(revision, "start", "session-A");
        observe(revision, "临时", false, false);
        observe(revision, "最终", false, false);
        equal("最终", field(call(revision, "prepare", "r1"), "text"), "unsent revision is safe");
    }
    private static void oneRequestAndPrefixProtection() throws Exception {
        Object tracker = empty();
        Object pending = prepared(tracker, "甲", "p1");
        observe(tracker, "甲乙", false, false);
        equal(null, call(tracker, "prepare", "p2"), "one in flight");
        equal(pending, call(tracker, "pending"), "pending identity is stable");
        equal(true, call(tracker, "receipt", "p1", true, "inserted"), "inserted receipt accepted");
        equal("乙", field(call(tracker, "prepare", "p2"), "text"), "queued suffix follows acknowledgement");
        observe(tracker, "甲丙", false, false);
        equal(true, call(tracker, "hasConflict"), "editing pending prefix is conflict");
        equal(false, call(tracker, "isActive"), "pending prefix conflict pauses");
        equal("甲乙", field(call(tracker, "pending"), "snapshot"), "original pending survives conflict");
        call(tracker, "receipt", "p2", true, "inserted");
        equal(false, call(tracker, "start", "session-B"), "conflict requires deliberate reset");
        equal(null, call(tracker, "prepare", "p3"), "no remote correction");
    }
    private static void invalidReceiptRetainsPending() throws Exception {
        Object tracker = empty();
        Object pending = prepared(tracker, "内容", "valid-id");
        equal(false, call(tracker, "receipt", "other-id", true, "inserted"), "wrong UUID rejected");
        equal(false, call(tracker, "receipt", "valid-id", false, "inserted"), "ok false rejected");
        equal(false, call(tracker, "receipt", "valid-id", true, "unknown"), "unknown status rejected");
        equal(pending, call(tracker, "pending"), "invalid receipts retain request");
        equal("", call(tracker, "sent"), "invalid receipt never advances sent prefix");
    }
    private static void savedTextNeedsDeliberateRecovery() throws Exception {
        Object tracker = empty();
        prepared(tracker, "已输入", "s1");
        call(tracker, "receipt", "s1", true, "inserted");
        observe(tracker, "已输入未输入\n保留", false, false);
        call(tracker, "prepare", "s2");
        call(tracker, "receipt", "s2", true, "saved");
        equal("已输入", call(tracker, "sent"), "saved does not mean inserted");
        equal("已输入未输入\n保留", call(tracker, "draft"), "saved preserves original draft");
        equal(true, call(tracker, "isSaved"), "saved recovery state persisted");
        equal(false, call(tracker, "start", "new-session"), "saved cannot silently rearm");
        equal("未输入\n保留", call(tracker, "unsentForReset"), "recovery retains uninserted raw text");
        call(tracker, "reset", call(tracker, "unsentForReset"));
        equal(false, call(tracker, "isActive"), "reset does not auto activate");
        call(tracker, "start", "new-session");
        observe(tracker, "未输入\n保留", false, false);
        equal("未输入 保留", field(call(tracker, "prepare", "s3"), "text"), "explicit recovery can emit retained text");
    }
    private static void normalizationKeepsOriginalOffsets() throws Exception {
        Object tracker = empty();
        String raw = "中文👨‍👩‍👧‍👦\r\n第二行\t末尾\r";
        Object pending = prepared(tracker, raw, "n1");
        equal("中文👨‍👩‍👧‍👦 第二行 末尾 ", field(pending, "text"), "CR LF TAB become spaces");
        equal(raw, field(pending, "snapshot"), "raw offsets preserved");
        call(tracker, "receipt", "n1", true, "inserted");
        observe(tracker, raw + "追加🙂", false, false);
        equal("追加🙂", field(call(tracker, "prepare", "n2"), "text"), "UTF-16 raw offset suffix safe");
        Object half = empty();
        call(half, "start", "session-A");
        observe(half, "\uD83D", false, false);
        equal(null, call(half, "prepare", "n3"), "unpaired surrogate withheld");
        observe(half, "🙂", false, false);
        equal("🙂", field(call(half, "prepare", "n3"), "text"), "complete surrogate accepted");
    }
    private static void restorationAndPauseNeverAutoRearm() throws Exception {
        Object tracker = empty();
        Object pending = prepared(tracker, "未确认", "stable-id");
        Object restored = tracker("", "未确认追加", pending, false);
        equal(false, call(restored, "isActive"), "restored paused");
        equal(pending, call(restored, "pending"), "restore exact pending identity");
        equal(false, call(restored, "start", "new-session"), "pending cannot be rebound to new session");
        equal("session-A", field(call(restored, "pending"), "session"), "old session preserved for retry");
        call(restored, "receipt", "stable-id", true, "inserted");
        equal(false, call(restored, "isActive"), "recovered receipt does not rearm");
        equal(null, call(restored, "prepare", "r2"), "recovered queued draft is not auto sent");
        call(restored, "start", "new-session");
        observe(restored, "未确认追加", false, false);
        equal("追加", field(call(restored, "prepare", "r2"), "text"), "explicit new session resumes suffix");
        call(restored, "pause");
        call(restored, "receipt", "r2", true, "inserted");
        observe(restored, "未确认追加后台", false, false);
        equal(null, call(restored, "prepare", "r3"), "late receipt cannot resume background input");
        Object legacy = tracker("已发", "已发旧草稿", null, false);
        equal(false, call(legacy, "isActive"), "legacy restored draft paused");
    }
    public static void main(String[] args) throws Exception {
        try {
            trackerClass = Class.forName("io.github.amxooo.voiceinput2pc.CommitTracker");
            pendingClass = Class.forName("io.github.amxooo.voiceinput2pc.CommitTracker$Pending");
        } catch (ClassNotFoundException e) {
            throw new AssertionError("Missing committed-input tracker; current timer cannot prove IME commit", e);
        }
        compositionOnlyEmitsFinalCommit();
        batchesAndRapidRevisionCoalesce();
        oneRequestAndPrefixProtection();
        invalidReceiptRetainsPending();
        savedTextNeedsDeliberateRecovery();
        normalizationKeepsOriginalOffsets();
        restorationAndPauseNeverAutoRearm();
        System.out.println(checks + " commit tracker checks passed");
    }
}
