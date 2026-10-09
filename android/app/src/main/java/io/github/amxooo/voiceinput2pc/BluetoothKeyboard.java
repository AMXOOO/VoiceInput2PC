package io.github.amxooo.voiceinput2pc;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothHidDevice;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Optional Bluetooth HID keyboard transport; no receiver software is required on the host. */
public final class BluetoothKeyboard {
    public interface Listener { void onState(String message); }
    private static final byte REPORT_ID = 1;
    private static final byte[] DESCRIPTOR = {
        0x05,0x01, 0x09,0x06, (byte)0xA1,0x01, (byte)0x85,REPORT_ID,
        0x05,0x07, 0x19,(byte)0xE0, 0x29,(byte)0xE7,
        0x15,0x00, 0x25,0x01, 0x75,0x01, (byte)0x95,0x08,
        (byte)0x81,0x02, (byte)0x95,0x01, 0x75,0x08, (byte)0x81,0x01,
        (byte)0x95,0x06, 0x75,0x08, 0x15,0x00, 0x25,0x65,
        0x05,0x07, 0x19,0x00, 0x29,0x65, (byte)0x81,0x00,
        (byte)0xC0
    };
    private final Context context;
    private final Listener listener;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private BluetoothAdapter adapter;
    private BluetoothHidDevice hid;
    private BluetoothDevice connected;
    private volatile boolean registered;
    private volatile boolean registrationPending;
    private volatile boolean closed;
    private final BluetoothHidDevice.Callback callback = new BluetoothHidDevice.Callback() {
        @Override public void onAppStatusChanged(BluetoothDevice pluggedDevice, boolean isRegistered) {
            registered = isRegistered;
            registrationPending = false;
            if (!isRegistered) connected = null;
            report(isRegistered ? "蓝牙键盘已就绪，请选择已配对电脑" : "蓝牙键盘未注册；返回应用后可重新初始化");
        }
        @Override public void onConnectionStateChanged(BluetoothDevice device, int state) {
            connected = state == BluetoothProfile.STATE_CONNECTED ? device : null;
            report(connected == null ? "蓝牙键盘未连接" : "蓝牙键盘已连接：" + safeName(device));
        }
    };
    public BluetoothKeyboard(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.listener = listener;
    }
    private void report(String message) { if (!closed) listener.onState(message); }
    public boolean hasPermission() {
        return Build.VERSION.SDK_INT < 31 ||
            context.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }
    public void start() {
        if (Build.VERSION.SDK_INT < 28) { report("系统不支持蓝牙 HID Device"); return; }
        if (!hasPermission()) { report("请先允许附近设备权限"); return; }
        BluetoothManager manager = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        adapter = manager == null ? null : manager.getAdapter();
        if (adapter == null || !adapter.isEnabled()) { report("请先打开手机蓝牙"); return; }
        if (hid != null) {
            if (!registered && !registrationPending) registerHid();
            else report(registered ? "蓝牙键盘已就绪" : "正在注册蓝牙键盘");
            return;
        }
        boolean requested = adapter.getProfileProxy(context, new BluetoothProfile.ServiceListener() {
            @Override public void onServiceConnected(int profile, BluetoothProfile proxy) {
                if (closed) { adapter.closeProfileProxy(profile, proxy); return; }
                hid = (BluetoothHidDevice) proxy;
                registerHid();
            }
            @Override public void onServiceDisconnected(int profile) {
                hid = null; registered = false; registrationPending = false; connected = null;
                report("蓝牙 HID 服务已断开");
            }
        }, BluetoothProfile.HID_DEVICE);
        report(requested ? "正在初始化蓝牙键盘" : "系统拒绝蓝牙 HID 服务");
    }
    private void registerHid() {
        if (closed || hid == null || registered || registrationPending) return;
        registrationPending = true;
        android.bluetooth.BluetoothHidDeviceAppSdpSettings sdp =
            new android.bluetooth.BluetoothHidDeviceAppSdpSettings(
                "手机万能输入法", "手机蓝牙键盘", "手机万能输入法", BluetoothHidDevice.SUBCLASS1_COMBO, DESCRIPTOR);
        boolean ok = hid.registerApp(sdp, null, null, executor, callback);
        if (!ok) {
            registrationPending = false;
            report("系统不允许注册蓝牙键盘，请保持应用前台后重试");
        }
    }
    public List<BluetoothDevice> paired() {
        List<BluetoothDevice> result = new ArrayList<>();
        if (!hasPermission() || adapter == null) return result;
        result.addAll(adapter.getBondedDevices());
        return result;
    }
    public void connect(BluetoothDevice device) {
        if (!hasPermission() || hid == null || !registered) { report("蓝牙键盘尚未就绪"); return; }
        if (!hid.connect(device)) report("连接请求失败，请检查电脑蓝牙配对");
        else report("正在连接：" + safeName(device));
    }
    public static String safeName(BluetoothDevice device) {
        if (device == null) return "未知设备";
        try { String name = device.getName(); return name == null ? device.getAddress() : name; }
        catch (SecurityException e) { return "已配对设备"; }
    }
    public boolean isConnected() { return hid != null && connected != null; }
    /** Reject the entire payload before transmission if HID cannot represent it faithfully. */
    public static String validateText(String text) {
        if (text == null || text.isEmpty()) return "请先输入文字";
        if (text.length() > 1000) return "单次最多发送1000个字符";
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch < 32 || ch > 126) return "蓝牙免安装模式暂只支持英文、数字和常用 ASCII 符号；中文请使用电脑接收端";
            if (key(ch) == null) return "存在无法转换的键盘字符";
        }
        return null;
    }
    /** US keyboard HID usage + modifier; the target host layout must match. */
    private static byte[] key(char c) {
        if (c >= 'a' && c <= 'z') return new byte[]{0,(byte)(4+c-'a')};
        if (c >= 'A' && c <= 'Z') return new byte[]{2,(byte)(4+c-'A')};
        if (c >= '1' && c <= '9') return new byte[]{0,(byte)(30+c-'1')};
        if (c == '0') return new byte[]{0,39};
        String plain = " -=[]\\;',./";
        int[] usage = {44,45,46,47,48,49,51,52,54,55,56};
        int ix = plain.indexOf(c);
        if (ix >= 0) return new byte[]{0,(byte)usage[ix]};
        String shifted = "!@#$%^&*()_+{}|:\"<>?";
        int[] shiftedUsage = {30,31,32,33,34,35,36,37,38,39,45,46,47,48,49,51,52,54,55,56};
        ix = shifted.indexOf(c);
        if (ix >= 0) return new byte[]{2,(byte)shiftedUsage[ix]};
        if (c == '`') return new byte[]{0,53};
        if (c == '~') return new byte[]{2,53};
        return null;
    }
    public void send(String text) {
        send(text, HidTextEncoder.Mode.ASCII);
    }
    public void send(String text, HidTextEncoder.Mode mode) {
        final java.util.List<HidTextEncoder.Stroke> strokes;
        try { strokes=HidTextEncoder.encode(text,mode); }
        catch (IllegalArgumentException invalid) { report(invalid.getMessage()); return; }
        if (!isConnected()) { report("请先连接电脑蓝牙"); return; }
        final BluetoothHidDevice targetHid=hid;
        final BluetoothDevice target=connected;
        executor.execute(() -> {
            int sent=0;
            try {
                for (HidTextEncoder.Stroke stroke:strokes) {
                    if (closed || hid != targetHid || connected != target)
                        throw new IllegalStateException("连接已中断");
                    if (!targetHid.sendReport(target,REPORT_ID,new byte[]{stroke.modifier,0,stroke.usage,0,0,0,0,0}))
                        throw new IllegalStateException("发送按键失败");
                    Thread.sleep(30);
                    if (!targetHid.sendReport(target,REPORT_ID,new byte[8]))
                        throw new IllegalStateException("释放按键失败");
                    Thread.sleep(30);
                    sent++;
                }
                report("已发送 "+sent+" 个 HID 按键事件，请在电脑输入框核对文字");
            } catch (Exception error) {
                try { targetHid.sendReport(target,REPORT_ID,new byte[8]); } catch (Exception ignored) {}
                report("发送中断，已尝试 "+sent+" 个按键；请核对电脑内容，不要盲目重发");
            }
        });
    }
    public void close() {
        closed = true;
        if (hid != null) {
            try { hid.unregisterApp(); } catch (RuntimeException ignored) {}
            if (adapter != null) adapter.closeProfileProxy(BluetoothProfile.HID_DEVICE, hid);
        }
        hid = null; connected = null; registered = false; registrationPending = false;
        executor.shutdown();
    }
}
