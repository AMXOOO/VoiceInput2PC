package io.github.amxooo.voiceinput2pc;

import android.test.ActivityInstrumentationTestCase2;
import android.test.InstrumentationTestRunner;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import java.lang.reflect.Field;

/** Opt-in only: requires an operator to prepare and verify the PC target immediately beforehand. */
public final class LiveRelayTest extends ActivityInstrumentationTestCase2<MainActivity> {
    public LiveRelayTest() { super(MainActivity.class); }
    private Object field(MainActivity activity, String name) throws Exception {
        Field field=MainActivity.class.getDeclaredField(name); field.setAccessible(true); return field.get(activity);
    }
    public void testOptInLiveCommittedInput() throws Exception {
        android.os.Bundle arguments=((InstrumentationTestRunner)getInstrumentation()).getArguments();
        boolean preview="true".equals(arguments.getString("preview"));
        if (!"true".equals(arguments.getString("live")) && !preview) return;
        String host=arguments.getString("host");
        if (host == null || host.trim().isEmpty()) fail("Pass the target PC with -e host <address>");
        getInstrumentation().getTargetContext().getSharedPreferences("voiceinput2pc",0).edit()
            .clear().putString("host",host).commit();
        MainActivity activity=getActivity();
        if (preview) return; // Prepare a clean paused screenshot; GET /health only, never activate.
        Button start=(Button)field(activity,"start");
        CommitTracker tracker=(CommitTracker)field(activity,"tracker");
        CommitEditText editor=(CommitEditText)field(activity,"editor");
        getInstrumentation().runOnMainSync(()->start.performClick());
        waitFor(()->tracker.isActive());
        String text="安卓链路验收：中文 123 👋。";
        getInstrumentation().runOnMainSync(()->editor.onCreateInputConnection(new EditorInfo()).commitText(text,1));
        waitFor(()->tracker.sent().equals(text));
        assertNull(tracker.pending());
        assertTrue(editor.hasFocus());
        getInstrumentation().runOnMainSync(()->start.performClick());
        assertFalse(tracker.isActive());
    }
    private void waitFor(java.util.concurrent.Callable<Boolean> predicate) throws Exception {
        long end=android.os.SystemClock.uptimeMillis()+15000;
        while(android.os.SystemClock.uptimeMillis()<end) {
            getInstrumentation().waitForIdleSync();
            if(predicate.call()) return;
            android.os.SystemClock.sleep(30);
        }
        fail("Live session/input was not acknowledged; inspect the phone status and PC target");
    }
}
