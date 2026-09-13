package io.github.amxooo.voiceinput2pc;

import android.content.SharedPreferences;
import android.content.Intent;
import android.net.Uri;
import android.test.ActivityInstrumentationTestCase2;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.widget.Button;
import org.json.JSONObject;
import java.lang.reflect.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Tests the real Activity and persistence; only the external HTTPS boundary is replaced. */
public final class MainActivityTest extends ActivityInstrumentationTestCase2<MainActivity> {
    private SharedPreferences prefs;
    private MainActivity activity;
    private Transport runningTransport;
    public MainActivityTest() { super(MainActivity.class); }
    @Override protected void setUp() throws Exception {
        super.setUp();
        prefs=getInstrumentation().getTargetContext().getSharedPreferences("voiceinput2pc",0);
        // This suite is run only in the dedicated test emulator and cannot reach the PC.
        prefs.edit().clear().commit();
        assertTrue(PairingStore.save(prefs, testPairing()));
    }
    private PairingConfig testPairing() {
        return new PairingConfig("127.0.0.1",23337,
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "abababababababababababababababababababababababababababababababab");
    }
    @Override protected void tearDown() throws Exception {
        try {
            if (runningTransport!=null) runningTransport.release.countDown();
            if (activity!=null && !activity.isDestroyed()) {
                ui(()->activity.finish());
                waitFor(()->activity.isDestroyed());
            }
            getInstrumentation().waitForIdleSync();
        } finally { super.tearDown(); }
    }
    private Object field(String name) throws Exception {
        Field field=MainActivity.class.getDeclaredField(name); field.setAccessible(true); return field.get(activity);
    }
    private void invoke(String name, Class<?>[] types, Object... args) {
        try { Method method=MainActivity.class.getDeclaredMethod(name,types); method.setAccessible(true); method.invoke(activity,args); }
        catch (Exception e) { throw new AssertionError(e); }
    }
    private CommitTracker tracker() throws Exception { return (CommitTracker)field("tracker"); }
    private CommitEditText editor() throws Exception { return (CommitEditText)field("editor"); }
    private void ui(Runnable action) { getInstrumentation().runOnMainSync(action); }
    private void waitFor(java.util.concurrent.Callable<Boolean> predicate) throws Exception {
        long end=android.os.SystemClock.uptimeMillis()+5000;
        while (android.os.SystemClock.uptimeMillis()<end) {
            getInstrumentation().waitForIdleSync();
            if (predicate.call()) return;
            android.os.SystemClock.sleep(20);
        }
        fail("Expected Activity state did not arrive; active="+tracker().isActive()+", draft="+tracker().draft()
            +", sent="+tracker().sent()+", pending="+(tracker().pending()!=null)
            +", interrupted="+editor().wasConnectionInterrupted()+", status="+((android.widget.TextView)field("status")).getText());
    }
    private final class Transport implements InvocationHandler {
        volatile int requests, sessions;
        volatile boolean durable, wrongId, block;
        volatile JSONObject last;
        final CountDownLatch entered=new CountDownLatch(1), release=new CountDownLatch(1), returned=new CountDownLatch(1);
        @Override public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            if (method.getName().equals("session")) {
                sessions++;
                return new JSONObject().put("ok",true).put("session","captured-session").put("note","ready");
            }
            JSONObject body=(JSONObject)args[1];
            if(body==null) return new JSONObject().put("ok",true).put("app","VoiceInput2PC").put("protocol",2).put("paused",false);
            requests++; last=new JSONObject(body.toString());
            JSONObject stored=new JSONObject(prefs.getString("pending","{}"));
            durable=stored.getString("id").equals(body.getString("id"))
                && stored.getString("session").equals("captured-session")
                && !prefs.getString("pendingSnapshot","").isEmpty();
            entered.countDown();
            if(block && !release.await(5,TimeUnit.SECONDS)) throw new AssertionError("test release timed out");
            JSONObject response=new JSONObject().put("ok",true)
                .put("id",wrongId ? "wrong-id" : body.getString("id")).put("status","inserted").put("note","dispatched");
            returned.countDown(); return response;
        }
    }
    private Transport startWithTransport() throws Exception {
        activity=getActivity();
        Transport transport=new Transport(); runningTransport=transport;
        Class<?> boundary;
        try { boundary=Class.forName("io.github.amxooo.voiceinput2pc.RelayTransport"); }
        catch (ClassNotFoundException e) { throw new AssertionError("HTTPS boundary must permit isolated lifecycle verification",e); }
        Field client=MainActivity.class.getDeclaredField("client"); client.setAccessible(true);
        Object replacement=Proxy.newProxyInstance(boundary.getClassLoader(),new Class<?>[]{boundary},transport);
        ui(()-> { try { client.set(activity,replacement); } catch(Exception e) { throw new AssertionError(e); } });
        ui(()->invoke("beginSession",new Class<?>[]{}));
        waitFor(()->tracker().isActive());
        return transport;
    }
    public void testEmptyPreferencesShowPairingScreen() throws Exception {
        prefs.edit().clear().commit();
        activity=getActivity();
        assertNull(field("tracker"));
        assertNotNull(field("pairingInput"));
        assertTrue(activity.getTitle().toString().contains("连接电脑"));
    }
    public void testMalformedViewIntentNeverReplacesStoredPairing() throws Exception {
        PairingConfig original=PairingStore.load(prefs);
        setActivityIntent(new Intent(Intent.ACTION_VIEW,
            Uri.parse("voiceinput2pc://pair?p=bad")));
        activity=getActivity();
        getInstrumentation().waitForIdleSync();
        assertEquals(original,PairingStore.load(prefs));
        assertNotNull(field("pairingInput"));
    }
    public void testCommitIsAutomaticAndDurableBeforeRequest() throws Exception {
        Transport transport=startWithTransport();
        CommitEditText editor=editor();
        final InputConnection[] connection=new InputConnection[1];
        ui(()-> {
            connection[0]=editor.onCreateInputConnection(new EditorInfo());
            connection[0].setComposingText("语音临时",1);
        });
        getInstrumentation().waitForIdleSync();
        assertEquals(0,transport.requests);
        ui(()->connection[0].commitText("语音完成🙂\n下一行",1));
        waitFor(()->tracker().sent().equals("语音完成🙂\n下一行"));
        assertTrue(transport.durable);
        assertEquals("语音完成🙂 下一行",transport.last.getString("text"));
        assertEquals(1,transport.requests);
        assertEquals("",prefs.getString("pending",""));
        assertTrue(editor.hasFocus());
    }
    public void testInvalidReceiptKeepsExactRequestForExplicitRetry() throws Exception {
        Transport transport=startWithTransport(); transport.wrongId=true;
        CommitEditText editor=editor();
        ui(()->editor.getText().append("保留这条"));
        waitFor(()->!tracker().isActive() && tracker().pending()!=null);
        CommitTracker.Pending pending=tracker().pending();
        assertEquals(pending.id,new JSONObject(prefs.getString("pending","{}")).getString("id"));
        assertEquals("",tracker().sent());
        transport.wrongId=false;
        ui(()->invoke("dispatch",new Class<?>[]{CommitTracker.Pending.class},pending));
        waitFor(()->tracker().pending()==null);
        assertEquals(pending.id,transport.last.getString("id"));
        assertEquals("captured-session",transport.last.getString("session"));
        assertEquals(1,transport.sessions);
        assertFalse(tracker().isActive());
    }
    public void testPauseAndLateReceiptCannotRearm() throws Exception {
        Transport transport=startWithTransport(); transport.block=true;
        CommitEditText editor=editor();
        ui(()->editor.getText().append("暂停之前"));
        assertTrue(transport.entered.await(5,TimeUnit.SECONDS));
        ui(()->getInstrumentation().callActivityOnPause(activity));
        assertFalse(tracker().isActive());
        assertEquals(0,activity.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        transport.release.countDown();
        waitFor(()->tracker().sent().equals("暂停之前"));
        ui(()-> { getInstrumentation().callActivityOnResume(activity); editor.getText().append("后台追加"); });
        getInstrumentation().waitForIdleSync();
        assertFalse(tracker().isActive());
        assertEquals(1,transport.requests);
    }
    public void testManualPauseRemainsAvailableDuringRequest() throws Exception {
        Transport transport=startWithTransport(); transport.block=true;
        CommitEditText editor=editor(); Button start=(Button)field("start");
        ui(()->editor.getText().append("正在请求"));
        assertTrue(transport.entered.await(5,TimeUnit.SECONDS));
        ui(()->editor.getText().append("排队的后缀"));
        assertTrue("Pause must remain usable during a slow HTTPS request",start.isEnabled());
        ui(()->start.performClick());
        assertFalse(tracker().isActive());
        assertNotNull(tracker().pending());
        transport.release.countDown();
        waitFor(()->tracker().sent().equals("正在请求"));
        getInstrumentation().waitForIdleSync();
        assertEquals(1,transport.requests);
        assertEquals("正在请求排队的后缀",tracker().draft());
    }
    public void testDestroyedCallbackCannotOverwriteNewDraft() throws Exception {
        Transport transport=startWithTransport(); transport.block=true;
        CommitEditText editor=editor();
        ui(()->editor.getText().append("待确认的原文"));
        assertTrue(transport.entered.await(5,TimeUnit.SECONDS));
        ui(()->activity.finish());
        waitFor(()->activity.isDestroyed());
        prefs.edit().putString("draft","后来保存的新草稿").commit();
        transport.release.countDown();
        assertTrue(transport.returned.await(5,TimeUnit.SECONDS));
        assertTrue(((java.util.concurrent.ExecutorService)field("worker")).awaitTermination(5,TimeUnit.SECONDS));
        getInstrumentation().waitForIdleSync();
        assertEquals("后来保存的新草稿",prefs.getString("draft",""));
        assertFalse(prefs.getString("pending","").isEmpty());
    }
    public void testLegacyPendingRestoreDoesNotSendOrRearm() throws Exception {
        prefs.edit().putString("draft","旧版文字").putString("pendingSnapshot","旧版文字")
            .putString("pending",new JSONObject().put("id","legacy-id").put("text","旧版文字").toString())
            .putBoolean("auto",true).commit();
        activity=getActivity();
        assertFalse(tracker().isActive());
        assertEquals("legacy-id",tracker().pending().id);
        assertEquals("",tracker().pending().session);
        assertFalse(((Button)field("start")).isEnabled());
        assertEquals(View.GONE,((Button)field("retry")).getVisibility());
        assertEquals("旧版文字",editor().getText().toString());
    }
    public void testIdleConnectionReplacementKeepsSessionReady() throws Exception {
        startWithTransport(); CommitEditText editor=editor();
        ui(()->editor.onCreateInputConnection(new EditorInfo()).closeConnection());
        assertTrue("An idle IME reconnect must not cancel an explicitly started session",tracker().isActive());
    }
    public void testUnfinishedConnectionClosePausesAndPreservesDraft() throws Exception {
        Transport transport=startWithTransport(); CommitEditText editor=editor();
        ui(()-> {
            InputConnection connection=editor.onCreateInputConnection(new EditorInfo());
            connection.beginBatchEdit(); connection.setComposingText("尚未确认的语音",1);
            connection.closeConnection();
        });
        getInstrumentation().waitForIdleSync();
        assertFalse("Closing uncommitted speech must pause the Activity",tracker().isActive());
        assertEquals("尚未确认的语音",tracker().draft());
        assertEquals(0,transport.requests);
    }
}
