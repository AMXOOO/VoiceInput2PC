package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Pattern;

/**
 * Starts the bundled Tailcat runtime as a localhost-only forwarding sidecar.
 * VoiceInput2PC always uses an ephemeral Tailcat client identity so it does not
 * depend on or mutate any standalone Tailcat configuration on the device.
 */
final class TailcatForwarder {
    private static final Map<String, TailcatForwarder> ACTIVE = new ConcurrentHashMap<>();
    private static final Pattern ADDRESS = Pattern.compile("tc[A-Za-z0-9_-]{20,4094}");

    private final Process process;
    private final int localPort;
    private final Deque<String> diagnostics = new ArrayDeque<>();

    private TailcatForwarder(Context context, String tailcatAddress, int remotePort) throws Exception {
        if (context == null) throw new IllegalArgumentException("Android context is required for Tailcat");
        File binary = new File(context.getApplicationInfo().nativeLibraryDir, "libtailcat.so");
        if (!binary.isFile()) {
            throw new Exception("阶段1/4：手机安装包里没有跨网络组件");
        }
        if (!binary.canExecute()) {
            // nativeLibraryDir should normally be executable; make this explicit for diagnostics.
            binary.setExecutable(true, true);
        }

        localPort = choosePort();
        ProcessBuilder builder = new ProcessBuilder(
                binary.getAbsolutePath(),
                "--key=new",
                "forward",
                tailcatAddress,
                localPort + ":" + remotePort);
        builder.redirectErrorStream(true);

        try {
            process = builder.start();
        } catch (Exception startFailure) {
            throw new Exception("阶段1/4：手机无法启动跨网络组件：" + safe(startFailure.getMessage()), startFailure);
        }

        Thread drain = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), java.nio.charset.StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) remember(line);
            } catch (Exception ignored) {
            }
        }, "voiceinput2pc-tailcat-log-drain");
        drain.setDaemon(true);
        drain.start();

        waitForListener();
    }

    static TailcatForwarder getOrStart(Context context, String address, int remotePort) throws Exception {
        String key = address + "\n" + remotePort;
        TailcatForwarder existing = ACTIVE.get(key);
        if (existing != null && existing.isAlive()) return existing;
        synchronized (ACTIVE) {
            existing = ACTIVE.get(key);
            if (existing != null && existing.isAlive()) return existing;
            TailcatForwarder created = new TailcatForwarder(context.getApplicationContext(), address, remotePort);
            ACTIVE.put(key, created);
            return created;
        }
    }

    int localPort() {
        return localPort;
    }

    private boolean isAlive() {
        try {
            process.exitValue();
            return false;
        } catch (IllegalThreadStateException running) {
            return true;
        }
    }

    private void waitForListener() throws Exception {
        long deadline = System.currentTimeMillis() + 12000;
        Exception last = null;
        while (System.currentTimeMillis() < deadline) {
            if (!isAlive()) {
                int code = process.exitValue();
                throw new Exception("阶段1/4：跨网络组件已退出（代码 " + code + diagnosticSuffix() + "）");
            }
            try (Socket socket = new Socket()) {
                socket.connect(new java.net.InetSocketAddress(
                        InetAddress.getLoopbackAddress(), localPort), 250);
                return;
            } catch (Exception failure) {
                last = failure;
                Thread.sleep(100);
            }
        }
        process.destroy();
        throw new Exception("阶段2/4：手机本地转发端口没有建立" + diagnosticSuffix(), last);
    }

    private void remember(String raw) {
        String value = safe(raw);
        if (value.isEmpty()) return;
        synchronized (diagnostics) {
            diagnostics.addLast(value);
            while (diagnostics.size() > 4) diagnostics.removeFirst();
        }
    }

    private String diagnosticSuffix() {
        synchronized (diagnostics) {
            if (diagnostics.isEmpty()) return "";
            StringBuilder out = new StringBuilder("：");
            boolean first = true;
            for (String line : diagnostics) {
                if (!first) out.append(" | ");
                first = false;
                out.append(line);
            }
            return out.toString();
        }
    }

    private static String safe(String raw) {
        if (raw == null) return "";
        String value = ADDRESS.matcher(raw.trim()).replaceAll("tc<redacted>");
        if (value.length() > 300) value = value.substring(0, 300);
        return value;
    }

    private static int choosePort() throws Exception {
        try (ServerSocket socket = new ServerSocket(
                0, 1, InetAddress.getLoopbackAddress())) {
            return socket.getLocalPort();
        }
    }
}
