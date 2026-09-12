package io.github.amxooo.voiceinput2pc;

import android.test.InstrumentationTestCase;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.widget.EditText;

/** Run on an Android device with the platform instrumentation runner. */
public final class CommitEditTextTest extends InstrumentationTestCase {
    private EditText editor(CommitTracker tracker) {
        try {
            Class<?> type = Class.forName("io.github.amxooo.voiceinput2pc.CommitEditText");
            EditText editor = (EditText) type.getConstructor(android.content.Context.class)
                .newInstance(getInstrumentation().getTargetContext());
            Runnable observer = () -> {
                try {
                    tracker.observe(editor.getText().toString(),
                        (Boolean) type.getMethod("hasComposition").invoke(editor),
                        (Boolean) type.getMethod("hasOpenEdit").invoke(editor));
                } catch (Exception e) { throw new AssertionError(e); }
            };
            type.getMethod("setEditObserver", Runnable.class).invoke(editor, observer);
            return editor;
        } catch (Exception e) { throw new AssertionError("Missing native commit observation", e); }
    }
    public void testCompositionAndBatchBoundariesPreserveEditable() throws Throwable {
        runTestOnUiThread(() -> {
            CommitTracker tracker = new CommitTracker("", "", null, false);
            tracker.start("test-session");
            EditText editor = editor(tracker);
            InputConnection connection = editor.onCreateInputConnection(new EditorInfo());
            assertNotNull(connection);
            assertTrue(connection.beginBatchEdit());
            assertTrue(connection.setComposingText("zhong", 1));
            assertEquals("zhong", editor.getText().toString());
            assertNull(tracker.prepare("id"));
            assertTrue(connection.setComposingText("中文", 1));
            assertEquals("中文", editor.getText().toString());
            assertNull(tracker.prepare("id"));
            assertTrue(connection.commitText("中文完成", 1));
            assertNull(tracker.prepare("id"));
            connection.endBatchEdit();
            assertEquals("中文完成", editor.getText().toString());
            assertEquals("中文完成", tracker.prepare("id").text);
        });
    }

    public void testFinishCompositionAndHardwarePasteFallback() throws Throwable {
        runTestOnUiThread(() -> {
            CommitTracker tracker = new CommitTracker("", "", null, false);
            tracker.start("test-session");
            EditText editor = editor(tracker);
            InputConnection connection = editor.onCreateInputConnection(new EditorInfo());
            connection.setComposingText("说话结果", 1);
            assertNull(tracker.prepare("speech"));
            connection.finishComposingText();
            assertEquals("说话结果", tracker.prepare("speech").text);
            assertTrue(tracker.receipt("speech", true, "inserted"));
            editor.getText().append("\n粘贴🙂");
            assertEquals(" 粘贴🙂", tracker.prepare("paste").text);
        });
    }
    public void testClosedBatchCannotBlockReplacementConnection() throws Throwable {
        runTestOnUiThread(() -> {
            CommitTracker tracker = new CommitTracker("", "", null, false);
            tracker.start("test-session");
            EditText editor = editor(tracker);
            InputConnection first = editor.onCreateInputConnection(new EditorInfo());
            first.beginBatchEdit(); first.setComposingText("暂存",1); first.closeConnection();
            InputConnection replacement = editor.onCreateInputConnection(new EditorInfo());
            editor.setText("");
            replacement.commitText("新输入",1);
            CommitTracker.Pending pending = tracker.prepare("new-id");
            assertNotNull("Closed connection batch state must not block its replacement", pending);
            assertEquals("新输入", pending.text);
        });
    }
}
