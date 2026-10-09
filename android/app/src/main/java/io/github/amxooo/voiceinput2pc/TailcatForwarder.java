package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Android Tailcat transport backed by an in-process Go library bridge.
 * No Linux CLI executable is launched from the Android app sandbox.
 */
final class TailcatForwarder {
    private static final Map<String, TailcatForwarder> ACTIVE = new ConcurrentHashMap<>();

    private final int localPort;

    private TailcatForwarder(Context context, String tailcatAddress, int remotePort) throws Exception {
        if (context == null) throw new IllegalArgumentException("Android context is required for Tailcat");
        try {
            localPort = TailcatNativeBridge.startForward(context, tailcatAddress, remotePort);
        } catch (Exception failure) {
            throw new Exception("阶段1/4：Tailcat Go Bridge 启动失败：" + safe(failure.getMessage()), failure);
        }
    }

    static TailcatForwarder getOrStart(Context context, String address, int remotePort) throws Exception {
        String key = address + "\n" + remotePort;
        TailcatForwarder existing = ACTIVE.get(key);
        if (existing != null) return existing;
        synchronized (ACTIVE) {
            existing = ACTIVE.get(key);
            if (existing != null) return existing;
            // Current bridge exposes one active forwarder. Re-pairing replaces it.
            TailcatNativeBridge.stop();
            ACTIVE.clear();
            TailcatForwarder created = new TailcatForwarder(
                    context.getApplicationContext(), address, remotePort);
            ACTIVE.put(key, created);
            return created;
        }
    }

    int localPort() {
        return localPort;
    }

    private static String safe(String raw) {
        String value = raw == null || raw.trim().isEmpty() ? "未知错误" : raw.trim();
        value = value.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        return value.length() > 320 ? value.substring(0, 320) : value;
    }
}
