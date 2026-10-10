package io.github.amxooo.voiceinput2pc;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Build;
import android.view.WindowInsets;
import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import org.json.JSONObject;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private CommitEditText editor;
    private TextView status, destination, counter;
    private Button start, fresh, retry, receive, sendFile;
    private Button pairingButton;
    private EditText pairingInput;
    private SharedPreferences prefs;
    private RelayTransport client;
    private PairingConfig currentPairing;
    private boolean scannerReturnToTyping;
    private RelayTransport receiveQueueClient;
    private CommitTracker tracker;
    private String host, receiveQueueHost, legacyPendingRaw = "";
    private boolean busy, loading, destroyed, resumed, storageBlocked, sendingText, receiveQueued;
    private boolean fileTransferSupported;
    private int activationEpoch, receiveQueueEpoch = -1;
    private final int green = Color.rgb(22,112,91);
    private final Runnable flush = this::transmitCommitted;
    private static final int PICK_FILE_REQUEST = 2606;

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private TextView label(String text, int size, int color) {
        TextView view = new TextView(this);
        view.setText(text); view.setTextSize(size); view.setTextColor(color);
        return view;
    }
    private LinearLayout.LayoutParams row(int height) {
        return new LinearLayout.LayoutParams(-1, height < 0 ? height : dp(height));
    }
    private void say(String text, boolean error) {
        status.setText(text); status.setTextColor(error ? Color.rgb(168,70,35) : green);
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        if (Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        prefs = getSharedPreferences("voiceinput2pc", MODE_PRIVATE);
        scannerReturnToTyping = savedInstanceState != null && savedInstanceState.getBoolean("scannerReturnToTyping", false);
        PairingConfig pairing = PairingStore.load(prefs);
        String incoming = incomingPairing(getIntent());
        if (incoming != null) {
            showPairingScreen("正在读取电脑配对码…");
            pairingInput.setText(incoming);
            importPairing(incoming);
        } else if (pairing == null) {
            showPairingScreen("请先在电脑接收端打开“配对手机”。");
        } else {
            showTypingScreen(pairing);
        }
    }

    @Override protected void onSaveInstanceState(Bundle outState) {
        outState.putBoolean("scannerReturnToTyping", scannerReturnToTyping);
        super.onSaveInstanceState(outState);
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String incoming = incomingPairing(intent);
        if (incoming != null) {
            clearQueuedReceive();
            if (tracker != null) { pauseLocal(); save(); }
            showPairingScreen("正在读取电脑配对码…");
            pairingInput.setText(incoming);
            importPairing(incoming);
        }
    }

    private String incomingPairing(Intent intent) {
        if (intent == null || !Intent.ACTION_VIEW.equals(intent.getAction())
                || intent.getData() == null) return null;
        return intent.getData().toString();
    }

    private void showPairingScreen(String message) {
        clearQueuedReceive();
        setTitle("连接电脑");
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        applyScreenInsets(layout);
        layout.setBackgroundColor(Color.rgb(247,248,244));
        TextView title = label("连接电脑", 22, Color.rgb(31,48,43));
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        layout.addView(title, row(-2));
        TextView guide = label("在电脑接收端点击“配对手机”，点击下方“扫码连接”；也可以粘贴完整配对码。",
                15, Color.DKGRAY);
        guide.setPadding(0, dp(10), 0, dp(16));
        layout.addView(guide, row(-2));
        Button scan = new Button(this);
        scan.setId(1002); scan.setText("扫码连接");
        scan.setOnClickListener(v -> launchScanner());
        layout.addView(scan, row(48));
        pairingInput = new EditText(this);
        pairingInput.setHint("粘贴 voiceinput2pc:// 开头的完整配对码");
        pairingInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                | InputType.TYPE_TEXT_VARIATION_URI);
        pairingInput.setMinLines(4);
        pairingInput.setGravity(android.view.Gravity.TOP | android.view.Gravity.START);
        layout.addView(pairingInput, new LinearLayout.LayoutParams(-1, 0, 1));
        status = label(message, 14, green);
        status.setPadding(0, dp(12), 0, dp(8));
        layout.addView(status, row(-2));
        pairingButton = new Button(this);
        pairingButton.setText("导入并连接");
        pairingButton.setTextColor(Color.WHITE);
        pairingButton.setBackgroundTintList(ColorStateList.valueOf(green));
        pairingButton.setOnClickListener(v -> importPairing(pairingInput.getText().toString().trim()));
        layout.addView(pairingButton, row(48));
        TextView safety = label("配对码相当于连接密码，只在自己的手机和电脑之间使用。仅扫码时申请相机权限，不需要麦克风权限。",
                12, Color.GRAY);
        safety.setPadding(0, dp(12), 0, 0);
        layout.addView(safety, row(-2));
        setContentView(layout);
    }

    private void applyScreenInsets(LinearLayout layout) {
        layout.setPadding(dp(12), dp(8), dp(12), dp(6));
        if (Build.VERSION.SDK_INT >= 30) {
            layout.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                android.graphics.Insets ime = insets.getInsets(WindowInsets.Type.ime());
                // Edge-to-edge content gets one inset; never add keyboard height twice.
                view.setPadding(bars.left + dp(12), bars.top + dp(8), bars.right + dp(12),
                        Math.max(bars.bottom, ime.bottom) + dp(6));
                return insets;
            });
        }
    }

    private void launchScanner() {
        IntentIntegrator scanner = new IntentIntegrator(this);
        scanner.setDesiredBarcodeFormats(IntentIntegrator.QR_CODE);
        scanner.setPrompt("将电脑配对二维码放入框内");
        scanner.setBeepEnabled(false);
        scanner.setBarcodeImageEnabled(false);
        scanner.setOrientationLocked(false);
        scanner.initiateScan();
    }

    private boolean canChangeConnection() {
        if (busy || (tracker != null && tracker.pending() != null)) {
            say("请先处理待确认文字，再调整连接。", true);
            return false;
        }
        if (tracker != null) { pauseLocal(); return save(); }
        return true;
    }

    private void showMore() {
        String[] items = {"扫码连接电脑", "发送文件到电脑", "连接方式", "连接诊断", "重新探测局域网", "使用说明"};
        new AlertDialog.Builder(this).setTitle("更多")
                .setItems(items, (dialog, which) -> {
                    if (which == 0) {
                        if (!canChangeConnection()) return;
                        scannerReturnToTyping = true;
                        showPairingScreen("扫描电脑接收端的配对二维码。");
                        launchScanner();
                    } else if (which == 1) {
                        if (sendFile.isEnabled()) sendFile.performClick();
                        else say("当前暂不能发送文件，请确认电脑连接和版本。", true);
                    } else if (which == 2) showConnectionModes();
                    else if (which == 3) showConnectionDiagnostics();
                    else if (which == 4) {
                        if (!canChangeConnection()) return;
                        try { client = createTransport(currentPairing); health(); }
                        catch (Exception failure) { say(pairingFailureText(failure), true); }
                    } else new AlertDialog.Builder(this).setTitle("使用说明")
                            .setMessage("先选中电脑输入框，再点开始。使用输入法麦克风输入，确认文字后自动发送。切到后台会暂停。文件单个不超过 200MB，保存到电脑 Downloads/VoiceInput2PC。")
                            .setPositiveButton("知道了", null).show();
                }).show();
    }

    private void showConnectionModes() {
        boolean local = prefs.getBoolean("lanOnly_" + currentPairing.fingerprint, false);
        new AlertDialog.Builder(this).setTitle("连接方式")
                .setSingleChoiceItems(new String[]{"自动：局域网优先，跨网络备用", "仅局域网"}, local ? 1 : 0,
                        (dialog, which) -> {
                            if (!canChangeConnection()) return;
                            if (!prefs.edit().putBoolean("lanOnly_" + currentPairing.fingerprint, which == 1).commit()) {
                                say("连接设置保存失败。", true); return;
                            }
                            dialog.dismiss(); showTypingScreen(currentPairing);
                        }).setNegativeButton("取消", null).show();
    }

    private void showConnectionDiagnostics() {
        String detail = "电脑局域网地址：" + currentPairing.host + ":" + currentPairing.port;
        if (client instanceof ConnectionManager) {
            ConnectionManager manager = (ConnectionManager) client;
            detail += "\n当前路径：" + manager.activeMode()
                    + "\n探测地址：" + manager.currentLanHost()
                    + "\n局域网探测：" + manager.lastLanFailure();
        } else detail += "\n连接设置：" + (prefs.getBoolean("lanOnly_" + currentPairing.fingerprint, false)
                ? "仅局域网" : currentPairing.transport);
        detail += "\n\n旁路由修改网关不会必然阻止直连；若探测失败，请检查电脑地址、防火墙及设备间路由。";
        new AlertDialog.Builder(this).setTitle("连接诊断").setMessage(detail)
                .setPositiveButton("关闭", null).show();
    }

    private void importPairing(String raw) {
        final PairingConfig candidate;
        try {
            candidate = PairingCodec.decode(raw);
        } catch (IllegalArgumentException invalid) {
            say("配对码无效，请重新扫描或完整粘贴。原有连接没有改变。", true);
            return;
        }
        pairingButton.setEnabled(false);
        say("正在核对电脑身份和连接凭据…", false);
        worker.execute(() -> {
            try {
                RelayTransport candidateClient = createTransport(candidate);
                JSONObject result = candidateClient.request(candidate.host, null);
                if (!Boolean.TRUE.equals(result.opt("ok"))
                        || !"VoiceInput2PC".equals(result.optString("app"))
                        || result.optInt("protocol") != 2) {
                    throw new Exception("接收端版本不兼容");
                }
                handler.post(() -> {
                    if (destroyed) return;
                    if (!PairingStore.save(prefs, candidate)) {
                        pairingButton.setEnabled(true);
                        say("手机无法保存连接配置，请检查存储空间后重试。", true);
                        return;
                    }
                    client = candidateClient;
                    showTypingScreen(candidate);
                    fileTransferSupported = hasFeature(result, "file-upload-v1");
                    updateControls();
                    String routeNote = routeNote(candidateClient);
                    say(result.optBoolean("paused")
                            ? "已连接" + routeNote + " · 请先在电脑启用输入，再选中输入框"
                            : "已连接" + routeNote + " · 先选中电脑输入框，再点开始", false);
                });
            } catch (Exception failure) {
                final String detail = pairingFailureText(failure);
                handler.post(() -> {
                    if (destroyed || pairingButton == null) return;
                    pairingButton.setEnabled(true);
                    say(detail, true);
                });
            }
        });
    }

    private RelayTransport createTransport(PairingConfig pairing) throws Exception {
        if (prefs.getBoolean("lanOnly_" + pairing.fingerprint, false)) {
            PairingConfig local = new PairingConfig(pairing.host, pairing.port, pairing.token,
                    pairing.fingerprint, PairingConfig.TRANSPORT_LAN, "", pairing.deviceId);
            return new RelayClient(this, local);
        }
        return pairing.isAuto() ? new ConnectionManager(this, pairing) : new RelayClient(this, pairing);
    }

    private String routeNote(RelayTransport transport) {
        if (!(transport instanceof ConnectionManager)) return currentPairing != null
                && !PairingConfig.TRANSPORT_TAILCAT.equals(currentPairing.transport) ? " · 本地直连" : "";
        String mode = ((ConnectionManager) transport).activeMode();
        if ("lan".equals(mode)) return " · 本地直连";
        if ("tailcat".equals(mode)) return " · 远程连接";
        return "";
    }

    private String pairingFailureText(Exception failure) {
        String message = failure == null ? "" : failure.getMessage();
        if (message == null || message.trim().isEmpty()) {
            message = failure == null ? "未知错误" : failure.getClass().getSimpleName();
        }
        message = message.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        if (message.length() > 360) message = message.substring(0, 360);
        return "连接失败 · " + message;
    }

    private void showTypingScreen(PairingConfig pairing) {
        currentPairing = pairing;
        clearQueuedReceive();
        fileTransferSupported = false;
        setTitle("语音输入电脑");
        try {
            host = prefs.getString("host", pairing.host);
            client = createTransport(pairing);
        } catch (Exception invalid) {
            showPairingScreen("保存的连接配置无法使用，请重新配对。");
            return;
        }
        String draft = prefs.getString("draft", ""), sent = prefs.getString("sent", "");
        String old = prefs.getString("pending", "");
        CommitTracker.Pending pending = null;
        legacyPendingRaw = prefs.getString("legacyPendingRaw", "");
        if (!old.isEmpty()) {
            String snapshot = prefs.getString("pendingSnapshot", draft);
            try {
                JSONObject value = new JSONObject(old);
                pending = new CommitTracker.Pending(value.getString("id"), snapshot,
                    value.getString("text"), value.optString("session", ""));
            } catch (Exception invalid) {
                legacyPendingRaw = old;
                pending = new CommitTracker.Pending("legacy-unconfirmed", snapshot, draft, "");
            }
        }
        tracker = new CommitTracker(sent, draft, pending, prefs.getBoolean("savedOnly", false));
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        applyScreenInsets(layout);
        layout.setBackgroundColor(Color.rgb(247,248,244));
        LinearLayout heading = new LinearLayout(this);
        heading.setGravity(android.view.Gravity.CENTER_VERTICAL);
        TextView title = label("语音输入电脑",20,Color.rgb(31,48,43));
        title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        heading.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button more = new Button(this); more.setId(1003); more.setText("更多");
        more.setOnClickListener(v -> showMore());
        heading.addView(more, new LinearLayout.LayoutParams(dp(72), dp(48)));
        layout.addView(heading,row(-2));
        destination = label(pairing.isAuto()
                ? "这台电脑 · 自动连接 · 更换 ›"
                : "电脑  " + host + "   · 更换 ›",13,Color.DKGRAY);
        destination.setPadding(0,dp(2),0,dp(4));
        destination.setOnClickListener(v -> {
            if (busy || tracker.pending() != null) {
                say("请先处理待确认文字，再更换电脑。", true);
                return;
            }
            pauseLocal(); save();
            showPairingScreen("请扫描新电脑接收端显示的二维码。");
        });
        layout.addView(destination,row(-2));
        status = label("已暂停 · 先选中电脑输入框，再点开始",14,green);
        layout.addView(status,row(-2));
        editor = new CommitEditText(this);
        editor.setId(1001); editor.setSaveEnabled(false);
        editor.setTextSize(19); editor.setTextColor(Color.rgb(30,39,35));
        editor.setGravity(android.view.Gravity.TOP | android.view.Gravity.START);
        editor.setHint("点开始后，用输入法的麦克风说话。已确认文字会自动输入电脑。");
        editor.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        editor.setImeOptions(EditorInfo.IME_FLAG_NO_EXTRACT_UI | EditorInfo.IME_ACTION_NONE);
        editor.setPadding(dp(10),dp(10),dp(10),dp(10)); editor.setMinLines(3);
        GradientDrawable card = new GradientDrawable();
        card.setColor(Color.WHITE); card.setCornerRadius(dp(14)); card.setStroke(dp(1),Color.rgb(215,224,217));
        editor.setBackground(card);
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(-1,0,1);
        inputParams.topMargin=dp(6); inputParams.bottomMargin=dp(4);
        layout.addView(editor,inputParams);
        counter = label("",12,Color.GRAY); layout.addView(counter,row(-2));
        retry = new Button(this); retry.setText("重试确认（同一条）");
        retry.setOnClickListener(v -> retryPending()); layout.addView(retry,row(-2));
        LinearLayout actions = new LinearLayout(this);
        fresh = new Button(this); fresh.setText("新一段");
        start = new Button(this); start.setText("开始输入到电脑");
        receive = new Button(this); receive.setText("接收");
        start.setTextColor(Color.WHITE); start.setBackgroundTintList(ColorStateList.valueOf(green));
        actions.addView(fresh,new LinearLayout.LayoutParams(0,dp(48),1));
        LinearLayout.LayoutParams startParams = new LinearLayout.LayoutParams(0,dp(48),2);
        startParams.leftMargin=dp(8); actions.addView(start,startParams);
        LinearLayout.LayoutParams receiveParams = new LinearLayout.LayoutParams(0,dp(48),1);
        receiveParams.leftMargin=dp(8); actions.addView(receive,receiveParams); layout.addView(actions,row(-2));
        sendFile = new Button(this); sendFile.setText("发送文件到电脑");
        setContentView(layout);
        loading=true; editor.setText(draft); editor.setSelection(editor.length()); loading=false;
        editor.setEditObserver(this::edited);
        start.setOnClickListener(v -> toggleStart()); fresh.setOnClickListener(v -> newDraft());
        receive.setOnClickListener(v -> receiveFromComputer());
        sendFile.setOnClickListener(v -> chooseFile());
        updateControls();
        if (pending != null) uncertainHint();
        else if (tracker.isSaved()) say("电脑只保存了文字，未自动输入。点“保留并重置”核对后恢复。",true);
        else if (tracker.hasConflict()) say("已输入部分发生修改。电脑原文不会改动，请保留并重置。",true);
        else if (!draft.isEmpty()) say("草稿已恢复，当前暂停。点开始前请核对电脑已有文字。",false);
        else health();
        probeCapabilities();
    }

    private void probeCapabilities() {
        final RelayTransport probeClient = client;
        final String address = host;
        worker.execute(() -> {
            try {
                JSONObject result = probeClient.request(address, null);
                final boolean supported = Boolean.TRUE.equals(result.opt("ok"))
                        && hasFeature(result, "file-upload-v1");
                handler.post(() -> {
                    if (destroyed || probeClient != client || !address.equals(host)) return;
                    fileTransferSupported = supported;
                    updateControls();
                });
            } catch (Exception ignored) {
                handler.post(() -> {
                    if (destroyed || probeClient != client || !address.equals(host)) return;
                    fileTransferSupported = false;
                    updateControls();
                });
            }
        });
    }

    private boolean hasFeature(JSONObject result, String feature) {
        org.json.JSONArray features = result.optJSONArray("features");
        if (features == null) return false;
        for (int i = 0; i < features.length(); i++) {
            if (feature.equals(features.optString(i))) return true;
        }
        return false;
    }

    private boolean save() {
        if (destroyed || tracker == null) return false;
        CommitTracker.Pending pending = tracker.pending();
        try {
            String message = pending == null ? "" : message(pending).toString();
            boolean stored = prefs.edit().putInt("schema",2).putString("host",host)
                .putString("draft",tracker.draft()).putString("sent",tracker.sent())
                .putString("pending",message).putString("pendingSnapshot",pending == null ? "" : pending.snapshot)
                .putBoolean("savedOnly",tracker.isSaved()).putString("legacyPendingRaw",legacyPendingRaw)
                .putBoolean("auto",false).commit();
            storageBlocked = !stored;
            if (!stored) { tracker.pause(); say("无法保存草稿，已暂停。请检查手机存储空间后重试。",true); }
            return stored;
        } catch (Exception e) {
            storageBlocked = true; tracker.pause(); say("无法保存待确认文字，已暂停。",true); return false;
        }
    }
    private JSONObject message(CommitTracker.Pending pending) throws Exception {
        return new JSONObject().put("id",pending.id).put("text",pending.text).put("session",pending.session);
    }
    private void updateControls() {
        if (destroyed || tracker == null) return;
        start.setText(tracker.isActive() ? "暂停输入" : "开始输入到电脑");
        start.setEnabled(tracker.isActive() || (!busy && !storageBlocked && tracker.pending() == null && !tracker.isSaved() && !tracker.hasConflict()));
        fresh.setEnabled(!busy);
        fresh.setText(tracker.pending() != null || tracker.isSaved() || tracker.hasConflict() ? "保留并重置" : "新一段");
        boolean cleanForReceive = !storageBlocked && !tracker.isSaved() && !tracker.hasConflict();
        receive.setEnabled((!busy && cleanForReceive && tracker.pending() == null)
            || (sendingText && !receiveQueued && cleanForReceive && tracker.pending() != null));
        retry.setVisibility(tracker.pending() != null && !tracker.pending().session.isEmpty() ? View.VISIBLE : View.GONE);
        retry.setEnabled(!busy);
        if (sendFile != null) sendFile.setEnabled(!busy && resumed && fileTransferSupported);
        counter.setText("电脑已接收输入 " + tracker.sent().codePointCount(0,tracker.sent().length())
            + " 字 · 本地草稿 " + tracker.draft().codePointCount(0,tracker.draft().length()) + " 字");
        if (tracker.isActive() && resumed) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
    private void edited() {
        if (loading || destroyed) return;
        tracker.observe(editor.getText().toString(),editor.hasComposition(),editor.hasOpenEdit());
        if (editor.wasConnectionInterrupted()) {
            pauseLocal(); say("输入法在确认文字前断开，已暂停。请核对草稿后重新开始。",true);
        }
        save(); updateControls(); handler.removeCallbacks(flush);
        if (tracker.hasConflict()) {
            say("已修改已输入或待确认的前缀，已暂停。电脑原文不会删除；请核对后重置。",true);
        } else if (resumed && tracker.isActive() && !busy) {
            // Coalesce within this UI turn; commit state comes from InputConnection, never elapsed time.
            handler.post(flush);
        }
    }
    private void pauseLocal() {
        activationEpoch++; tracker.pause(); handler.removeCallbacks(flush); updateControls();
    }
    private void toggleStart() {
        if (destroyed || !resumed) return;
        if (tracker.isActive()) {
            pauseLocal(); save();
            say(busy ? "已暂停后续输入；已发出的这条请求仍可能完成，请等待确认。" : "已暂停 · 再次开始时会重新确认电脑窗口",false);
            return;
        }
        if (busy) return;
        if (tracker.pending() != null || tracker.isSaved() || tracker.hasConflict()) return;
        if (!tracker.unsentForReset().isEmpty()) {
            new AlertDialog.Builder(this).setTitle("开始自动输入")
                .setMessage("开始后，草稿中尚未输入的文字会自动进入电脑当前输入框。请先核对电脑内容并选中目标输入框。")
                .setNegativeButton("取消",null).setPositiveButton("开始",(d,w)->beginSession()).show();
        } else beginSession();
    }
    private void beginSession() {
        if (busy || destroyed || !resumed) return;
        pauseLocal(); final int attempt = activationEpoch;
        final String address = host;
        busy=true; updateControls(); say("正在确认电脑输入窗口…",false);
        worker.execute(() -> {
            try {
                JSONObject result = client.session(address);
                handler.post(() -> {
                    if (destroyed) return;
                    busy=false;
                    if (!resumed || attempt != activationEpoch) { updateControls(); return; }
                    Object session = result.opt("session");
                    if (!Boolean.TRUE.equals(result.opt("ok")) || !(session instanceof String) || ((String)session).isEmpty()) {
                        say(result.optString("note","电脑未建立输入会话，请检查接收端版本和目标输入框。"),true);
                    } else if (tracker.start((String)session)) {
                        say("正在输入 · 用手机输入法麦克风说话，确认文字后自动输入电脑",false);
                        editor.requestFocus(); editor.setSelection(editor.length());
                        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(editor,InputMethodManager.SHOW_IMPLICIT);
                        edited();
                    }
                    updateControls();
                });
            } catch (Exception e) {
                handler.post(() -> {
                    if (destroyed) return;
                    busy=false; updateControls();
                    if (attempt == activationEpoch) say("未能开始。请确认电脑接收端已启动、处于启用状态，并选中输入框。",true);
                });
            }
        });
    }
    private void transmitCommitted() {
        if (destroyed || !resumed || busy || !tracker.isActive()) return;
        tracker.observe(editor.getText().toString(),editor.hasComposition(),editor.hasOpenEdit());
        if (tracker.hasConflict()) { pauseLocal(); save(); return; }
        String unsent = tracker.unsentForReset();
        if (unsent.codePointCount(0,unsent.length()) > 20000) {
            pauseLocal(); save(); say("未输入文字超过 20000 字，请先分段整理草稿。",true); return;
        }
        CommitTracker.Pending pending = tracker.prepare(UUID.randomUUID().toString());
        if (pending != null) dispatch(pending);
    }
    private void dispatch(CommitTracker.Pending pending) {
        if (destroyed || busy || !resumed) return;
        // Exact UUID, session, raw snapshot and transmitted text are durable BEFORE HTTPS.
        if (!save()) { updateControls(); return; }
        final JSONObject body;
        try { body = message(pending); }
        catch (Exception e) { pauseLocal(); uncertainHint(); return; }
        final String address = host;
        busy=true; sendingText=true; updateControls(); say("正在输入电脑…",false);
        worker.execute(() -> {
            try {
                JSONObject result = client.request(address,body);
                handler.post(() -> {
                    if (destroyed) return;
                    busy=false; sendingText=false;
                    Object id = result.opt("id"), resultStatus = result.opt("status");
                    boolean valid = id instanceof String && resultStatus instanceof String
                        && tracker.receipt((String)id,Boolean.TRUE.equals(result.opt("ok")),(String)resultStatus);
                    if (!valid) { clearQueuedReceive(); pauseLocal(); save(); uncertainHint(); return; }
                    if (!save()) { clearQueuedReceive(); updateControls(); return; }
                    RelayTransport queuedClient = receiveQueueClient;
                    String queuedHost = receiveQueueHost;
                    boolean runQueuedReceive = queuedReceiveIsCurrent() && tracker.pending() == null
                        && !tracker.isSaved() && !tracker.hasConflict();
                    clearQueuedReceive();
                    if (runQueuedReceive) {
                        beginReceiveFromComputer(queuedClient,queuedHost,activationEpoch);
                        return;
                    }
                    updateControls();
                    if (tracker.isSaved()) {
                        say(result.optString("note","电脑只保存了文字，未自动输入。") + " 请核对后保留并重置。",true);
                    } else if (tracker.hasConflict()) {
                        say("电脑已接收待确认文字，但手机前缀被改过。当前暂停，请核对并重置。",true);
                    } else if (tracker.isActive() && resumed) {
                        say("已交给电脑输入 · 可继续说话",false); handler.post(flush);
                    } else say("待确认文字已交给电脑输入，当前仍暂停。",false);
                });
            } catch (Exception e) {
                handler.post(() -> {
                    if (destroyed) return;
                    busy=false; sendingText=false; clearQueuedReceive(); pauseLocal(); save(); uncertainHint();
                });
            }
        });
    }
    private void uncertainHint() {
        updateControls();
        if (tracker.pending() != null && tracker.pending().session.isEmpty())
            say("保留了旧版待确认文字。请先核对电脑是否已有，再点“保留并重置”；不会自动重发。",true);
        else say("这条文字是否已输入尚未确认。点“重试确认”沿用原编号；不要重新输入同一段。",true);
    }
    private void retryPending() {
        if (busy || destroyed || !resumed || tracker.pending() == null || tracker.pending().session.isEmpty()) return;
        pauseLocal();
        new AlertDialog.Builder(this).setTitle("重试确认同一条文字")
            .setMessage("将沿用原编号和原输入会话。电脑若已处理，会返回原结果；若会话已失效，只保存文字。确认后仍保持暂停。")
            .setNegativeButton("取消",null).setPositiveButton("重试确认",(d,w)-> {
                if (tracker.pending() != null) dispatch(tracker.pending());
            }).show();
    }
    private void receiveFromComputer() {
        if (destroyed || !resumed || storageBlocked || tracker.isSaved() || tracker.hasConflict()) return;
        if (busy) {
            if (!sendingText || receiveQueued || tracker.pending() == null) return;
            pauseLocal();
            receiveQueued=true;
            receiveQueueEpoch=activationEpoch;
            receiveQueueHost=host;
            receiveQueueClient=client;
            if (!save()) { clearQueuedReceive(); updateControls(); return; }
            updateControls();
            say("已暂停后续输入 · 当前文字确认后自动接收",false);
            return;
        }
        if (tracker.pending() != null) return;
        pauseLocal();
        if (!save()) { updateControls(); return; }
        beginReceiveFromComputer(client,host,activationEpoch);
    }
    private void beginReceiveFromComputer(RelayTransport receiveClient, String address, int attempt) {
        busy=true; updateControls(); say("正在接收电脑文字…",false);
        worker.execute(() -> {
            try {
                JSONObject result=receiveClient.receive(address);
                handler.post(() -> {
                    if (destroyed) return;
                    busy=false;
                    if (!resumed || attempt != activationEpoch || receiveClient != client
                            || !address.equals(host)) { updateControls(); return; }
                    if (!Boolean.TRUE.equals(result.opt("ok"))) {
                        updateControls(); say("电脑没有返回可用文字，请稍后重试。",true); return;
                    }
                    if (!result.optBoolean("available",false)) {
                        updateControls(); say("电脑暂无待接收文字。先在电脑复制文字并点“发送剪贴板到手机”。",false); return;
                    }
                    Object itemId=result.opt("id"), itemText=result.opt("text");
                    if (!(itemId instanceof String) || !(itemText instanceof String)
                            || !validReceived((String)itemId,(String)itemText)) {
                        updateControls(); say("电脑返回的文字格式不正确，原草稿已保留。",true); return;
                    }
                    String id=(String)itemId, text=(String)itemText;
                    loading=true; tracker.reset(text); legacyPendingRaw="";
                    editor.setText(text); editor.setSelection(editor.length()); loading=false;
                    if (!save()) { updateControls(); return; }
                    updateControls(); say("已接收电脑文字 · 当前保持暂停",false);
                    worker.execute(() -> acknowledgeReceived(receiveClient,address,id,attempt));
                });
            } catch(Exception e) {
                handler.post(() -> {
                    if (destroyed) return;
                    busy=false; updateControls();
                    if (attempt == activationEpoch)
                        say("接收失败。请确认电脑接收端已启动、两端网络可达，然后重试。",true);
                });
            }
        });
    }
    private void acknowledgeReceived(RelayTransport receiveClient, String address, String id, int attempt) {
        try {
            JSONObject result=receiveClient.acknowledge(address,id);
            Object resultId=result.opt("id");
            if (!Boolean.TRUE.equals(result.opt("ok")) || !(resultId instanceof String)
                    || !id.equals(resultId) || !"received".equals(result.optString("status")))
                throw new Exception("invalid acknowledgement");
        } catch(Exception e) {
            handler.post(() -> {
                if (!destroyed && attempt == activationEpoch && receiveClient == client
                        && address.equals(host))
                    say("文字已接收；电脑尚未确认，下次可能再次收到同一条。",true);
            });
        }
    }
    private boolean queuedReceiveIsCurrent() {
        return receiveQueued && receiveQueueEpoch == activationEpoch
            && receiveQueueClient == client && receiveQueueHost != null
            && receiveQueueHost.equals(host);
    }
    private void clearQueuedReceive() {
        receiveQueued=false;
        receiveQueueEpoch=-1;
        receiveQueueHost=null;
        receiveQueueClient=null;
    }
    private boolean validReceived(String id, String text) {
        if (!id.matches("[A-Za-z0-9_-]{1,80}") || text.isEmpty()
                || text.codePointCount(0,text.length())>20000) return false;
        for (int i=0;i<text.length();i++) {
            char c=text.charAt(i);
            if (c<32 && c!='\r' && c!='\n' && c!='\t') return false;
            if (Character.isHighSurrogate(c)) {
                if (++i>=text.length() || !Character.isLowSurrogate(text.charAt(i))) return false;
            } else if (Character.isLowSurrogate(c)) return false;
        }
        return true;
    }
    private void chooseFile() {
        if (busy || destroyed || !resumed) return;
        if (tracker != null && tracker.isActive()) {
            pauseLocal();
            save();
        }
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, PICK_FILE_REQUEST);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        IntentResult scanned = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (scanned != null) {
            if (scanned.getContents() != null) {
                // Camera UI may outlive this Activity after background process recreation.
                showPairingScreen("正在读取扫码结果…");
                pairingInput.setText(scanned.getContents());
                importPairing(scanned.getContents());
            } else if (scannerReturnToTyping && currentPairing != null) {
                showTypingScreen(currentPairing);
            } else say("已取消扫码，可重新扫描或粘贴配对码。", false);
            scannerReturnToTyping = false;
            return;
        }
        if (requestCode != PICK_FILE_REQUEST || resultCode != RESULT_OK
                || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        try {
            int flags = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
            getContentResolver().takePersistableUriPermission(uri, flags);
        } catch (Exception ignored) {
        }
        sendSelectedFile(uri);
    }

    private void sendSelectedFile(Uri uri) {
        if (busy || destroyed) return;
        busy = true;
        updateControls();
        say("正在读取文件并计算 SHA-256…", false);
        final String address = host;
        final RelayTransport transferClient = client;
        worker.execute(() -> {
            try {
                AndroidFileTransfer.Metadata metadata = AndroidFileTransfer.inspect(
                        getContentResolver(), uri, (done, total) -> {
                            if (done == 0) return;
                            final long mb = done / (1024 * 1024);
                            handler.post(() -> {
                                if (!destroyed) say("正在校验文件 · 已读取 " + mb + " MB", false);
                            });
                        });
                handler.post(() -> {
                    if (!destroyed) say("准备发送 " + metadata.name + " · "
                            + formatBytes(metadata.size), false);
                });
                JSONObject result = AndroidFileTransfer.upload(
                        getContentResolver(), uri, metadata, transferClient, address,
                        (sent, total) -> {
                            final int percent = total <= 0 ? 0 : (int)Math.min(100, sent * 100 / total);
                            handler.post(() -> {
                                if (!destroyed) say("正在发送 " + metadata.name + " · " + percent + "%", false);
                            });
                        });
                String savedName = result.optString("name", metadata.name);
                handler.post(() -> {
                    if (destroyed) return;
                    busy = false;
                    updateControls();
                    say("文件已发送到电脑 · " + savedName, false);
                });
            } catch (Exception error) {
                final String detail = safeFileError(error);
                handler.post(() -> {
                    if (destroyed) return;
                    busy = false;
                    updateControls();
                    say("文件发送失败 · " + detail + " · 可重新选择同一文件续传", true);
                });
            }
        });
    }

    private String safeFileError(Exception error) {
        String message = error == null ? "" : error.getMessage();
        if (message == null || message.trim().isEmpty()) {
            message = error == null ? "未知错误" : error.getClass().getSimpleName();
        }
        message = message.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        return message.length() > 220 ? message.substring(0, 220) : message;
    }

    private String formatBytes(long bytes) {
        if (bytes >= 1024L * 1024L) {
            return String.format(java.util.Locale.ROOT, "%.1f MB", bytes / (1024.0 * 1024.0));
        }
        if (bytes >= 1024L) {
            return String.format(java.util.Locale.ROOT, "%.1f KB", bytes / 1024.0);
        }
        return bytes + " B";
    }

    private void newDraft() {
        if (busy || destroyed) return;
        pauseLocal();
        if (tracker.pending() != null) {
            new AlertDialog.Builder(this).setTitle("先核对电脑内容")
                .setMessage("这条文字可能已经输入。建议先重试确认。若无法确认，请在电脑逐字核对，再选择：已有则只保留后续文字；没有则保留全部未输入文字。")
                .setNegativeButton("取消",null)
                .setNeutralButton("电脑已有这条",(d,w)-> {
                    CommitTracker.Pending pending = tracker.pending();
                    String draft = tracker.draft();
                    if (!draft.startsWith(pending.snapshot)) {
                        say("手机前缀已改动，无法自动区分。请先把前缀恢复为待确认原文，再核对重置。",true); return;
                    }
                    resetDraft(draft.substring(pending.snapshot.length()));
                })
                .setPositiveButton("电脑没有，保留",(d,w)->resetDraft(tracker.unsentForReset())).show();
        } else if (tracker.isSaved() || tracker.hasConflict() || !tracker.unsentForReset().isEmpty()) {
            new AlertDialog.Builder(this).setTitle("保留文字，重新开始一段")
                .setMessage(tracker.hasConflict()
                    ? "已输入部分被修改，电脑原文仍在。将保留整份草稿作为新一段；再次开始前请手动删去草稿中不需重复输入的部分。"
                    : "将保留尚未输入的文字并重置状态。核对电脑输入框后，需要再点开始才会输入。")
                .setNegativeButton("取消",null).setPositiveButton("保留并重置",(d,w)->resetDraft(tracker.unsentForReset())).show();
        } else resetDraft("");
    }
    private void resetDraft(String retained) {
        if (destroyed || busy) return;
        loading=true; tracker.reset(retained); legacyPendingRaw="";
        editor.setText(retained); editor.setSelection(editor.length()); loading=false;
        save(); updateControls(); say("已暂停，新一段已准备好。核对电脑输入框后再点开始。",false);
        editor.requestFocus();
    }
    private void health() {
        final String address=host;
        final RelayTransport probeClient = client;
        worker.execute(() -> {
            try {
                JSONObject result=probeClient.request(address,null);
                handler.post(() -> {
                    if (destroyed || probeClient != client || busy || tracker.isActive() || tracker.pending()!=null || tracker.isSaved() || tracker.hasConflict()) return;
                    if (!Boolean.TRUE.equals(result.opt("ok")) || !"VoiceInput2PC".equals(result.optString("app")) || result.optInt("protocol") != 2) {
                        say("电脑接收端需要更新到远程键盘版本。",true);
                    } else {
                        fileTransferSupported = hasFeature(result, "file-upload-v1");
                        updateControls();
                        String routeNote = routeNote(probeClient);
                        say(result.optBoolean("paused") ? "已连接" + routeNote + " · 请先在电脑启用输入，再选中输入框" : "已连接" + routeNote + " · 先选中电脑输入框，再点开始",false);
                    }
                });
            } catch(Exception e) {
                handler.post(() -> {
                    if (!destroyed && probeClient == client && !busy && !tracker.isActive() && tracker.pending()==null && !tracker.isSaved() && !tracker.hasConflict())
                        say(pairingFailureText(e),true);
                });
            }
        });
    }
    @Override public void onResume() { super.onResume(); resumed=true; if(tracker!=null) updateControls(); }
    @Override public void onPause() {
        resumed=false;
        clearQueuedReceive();
        if (tracker!=null) { pauseLocal(); save(); say("已暂停 · 回到前台后请重新点开始",false); }
        super.onPause();
    }
    @Override public void onDestroy() {
        destroyed=true; clearQueuedReceive(); handler.removeCallbacksAndMessages(null); worker.shutdown(); super.onDestroy();
    }
}
