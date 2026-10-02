package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Starts the bundled tailcat static binary as a localhost-only forwarding sidecar.
 * The VoiceInput2PC application protocol still runs over HTTPS with its own token
 * and certificate fingerprint; tailcat only provides the encrypted cross-network tunnel.
 */
final class TailcatForwarder {
    private static final Map<String, TailcatForwarder> ACTIVE = new ConcurrentHashMap<>();

    private final Process process;
    private final int localPort;

    private TailcatForwarder(Context context, String tailcatAddress, int remotePort) throws Exception {
        if (context == null) throw new IllegalArgumentException("Android context is required for Tailcat");
        File binary = new File(context.getApplicationInfo().nativeLibraryDir, "libtailcat.so");
        if (!binary.isFile()) throw new Exception("Tailcat 组件未包含在当前安装包中");

        localPort = choosePort();
        ProcessBuilder builder = new ProcessBuilder(
                binary.getAbsolutePath(),
                "forward",
                tailcatAddress,
                localPort + ":" + remotePort);
        builder.redirectErrorStream(true);
        process = builder.start();
        Thread drain = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), java.nio.charset.StandardCharsets.UTF_8))) {
                while (reader.readLine() != null) {
                    // Do not log output: the tailcat address is connection-sensitive.
                }
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
        long deadline = System.currentTimeMillis() + 7000;
        Exception last = null;
        while (System.currentTimeMillis() < deadline) {
            if (!isAlive()) throw new Exception("Tailcat 通道启动失败");
            try (Socket socket = new Socket()) {
                socket.connect(new java.net.InetSocketAddress(
                        InetAddress.getLoopbackAddress(), localPort), 200);
                return;
            } catch (Exception failure) {
                last = failure;
                Thread.sleep(80);
            }
        }
        process.destroy();
        throw new Exception("Tailcat 本地通道启动超时", last);
    }

    private static int choosePort() throws Exception {
        try (ServerSocket socket = new ServerSocket(
                0, 1, InetAddress.getLoopbackAddress())) {
            return socket.getLocalPort();
        }
    }
}
