package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.X509Certificate;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

public final class RelayClient implements RelayTransport {
    private final String token;
    private final int port;
    private final SSLContext context;
    private final String forcedHost;
    private final int connectTimeoutMs;
    private final int readTimeoutMs;

    public RelayClient(PairingConfig pairing) throws Exception {
        this(null, pairing, 10000, 20000);
    }

    public RelayClient(Context androidContext, PairingConfig pairing) throws Exception {
        this(androidContext, pairing, 10000, 20000);
    }

    public RelayClient(Context androidContext, PairingConfig pairing,
                       int connectTimeoutMs, int readTimeoutMs) throws Exception {
        if (pairing == null) throw new IllegalArgumentException("连接配置缺失");
        token = pairing.token;
        this.connectTimeoutMs = connectTimeoutMs;
        this.readTimeoutMs = readTimeoutMs;
        if (pairing.isTailcat()) {
            TailcatForwarder forwarder = TailcatForwarder.getOrStart(
                    androidContext, pairing.tailcatAddress, pairing.port);
            port = forwarder.localPort();
            forcedHost = "127.0.0.1";
        } else {
            port = pairing.port;
            forcedHost = null;
        }
        final String fingerprint = pairing.fingerprint;
        context = SSLContext.getInstance("TLS");
        context.init(null, new TrustManager[]{new X509TrustManager() {
            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            public void checkClientTrusted(X509Certificate[] chain, String type) throws java.security.cert.CertificateException {
                throw new java.security.cert.CertificateException("Client certificates unsupported");
            }
            public void checkServerTrusted(X509Certificate[] chain, String type) throws java.security.cert.CertificateException {
                try {
                    if (chain == null || chain.length == 0) throw new Exception();
                    chain[0].checkValidity();
                    byte[] digest = MessageDigest.getInstance("SHA-256").digest(chain[0].getEncoded());
                    StringBuilder hex = new StringBuilder();
                    for (byte b : digest) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
                    if (!MessageDigest.isEqual(hex.toString().getBytes(StandardCharsets.US_ASCII),
                            fingerprint.getBytes(StandardCharsets.US_ASCII))) throw new Exception();
                } catch (Exception e) {
                    throw new java.security.cert.CertificateException("电脑身份不匹配");
                }
            }
        }}, null);
    }

    public JSONObject request(String host, JSONObject body) throws Exception {
        return request(host, body == null ? "/health" : "/text", body);
    }

    public JSONObject session(String host) throws Exception {
        return request(host, "/session", new JSONObject());
    }

    public JSONObject receive(String host) throws Exception {
        return request(host, "/outbox", null);
    }

    public JSONObject acknowledge(String host, String id) throws Exception {
        return request(host, "/outbox/ack", new JSONObject().put("id", id));
    }

    public JSONObject fileBegin(String host, JSONObject metadata) throws Exception {
        return request(host, "/file/begin", metadata);
    }

    public JSONObject fileComplete(String host, String transferId) throws Exception {
        return request(host, "/file/complete", new JSONObject().put("id", transferId));
    }

    public JSONObject fileChunk(String host, String transferId, long offset,
                                byte[] data, int length) throws Exception {
        if (data == null || length <= 0 || length > data.length || length > 1024 * 1024) {
            throw new IllegalArgumentException("文件分块无效");
        }
        String target = forcedHost == null ? host : forcedHost;
        if (!target.matches("[A-Za-z0-9.-]+")) throw new Exception("电脑地址格式不正确");
        URL url = new URL("https://" + target + ":" + port + "/file/chunk");
        HttpsURLConnection conn = (HttpsURLConnection) url.openConnection();
        configure(conn);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/octet-stream");
        conn.setRequestProperty("X-Transfer-Id", transferId);
        conn.setRequestProperty("X-Transfer-Offset", Long.toString(offset));
        conn.setFixedLengthStreamingMode(length);
        try {
            try (java.io.OutputStream stream = conn.getOutputStream()) {
                stream.write(data, 0, length);
            }
            return readJsonResponse(conn);
        } finally {
            conn.disconnect();
        }
    }

    private JSONObject request(String host, String path, JSONObject body) throws Exception {
        String target = forcedHost == null ? host : forcedHost;
        if (!target.matches("[A-Za-z0-9.-]+")) throw new Exception("电脑地址格式不正确");
        URL url = new URL("https://" + target + ":" + port + path);
        final HttpsURLConnection conn;
        try {
            conn = (HttpsURLConnection) url.openConnection();
        } catch (Exception openFailure) {
            throw new Exception("阶段3/4：无法打开电脑连接：" + safeMessage(openFailure), openFailure);
        }
        configure(conn);
        try {
            if (body != null) {
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                byte[] data = body.toString().getBytes(StandardCharsets.UTF_8);
                conn.setFixedLengthStreamingMode(data.length);
                try (java.io.OutputStream stream = conn.getOutputStream()) { stream.write(data); }
            }
            return readJsonResponse(conn);
        } finally { conn.disconnect(); }
    }

    private void configure(HttpsURLConnection conn) {
        conn.setSSLSocketFactory(context.getSocketFactory());
        // Server identity is pinned to the certificate fingerprint, not the tunnel hostname.
        conn.setHostnameVerifier((name, session) -> true);
        conn.setInstanceFollowRedirects(false);
        conn.setConnectTimeout(connectTimeoutMs);
        conn.setReadTimeout(readTimeoutMs);
        conn.setRequestProperty("Authorization", "Bearer " + token);
        conn.setRequestProperty("Connection", "close");
    }

    private JSONObject readJsonResponse(HttpsURLConnection conn) throws Exception {
        final int code;
        try {
            code = conn.getResponseCode();
        } catch (javax.net.ssl.SSLHandshakeException tlsFailure) {
            throw new Exception("电脑证书验证失败：" + safeMessage(tlsFailure), tlsFailure);
        } catch (java.net.ConnectException connectFailure) {
            throw new Exception("连接没有到达电脑：" + safeMessage(connectFailure), connectFailure);
        } catch (java.net.SocketTimeoutException timeout) {
            throw new Exception("连接电脑超时：" + safeMessage(timeout), timeout);
        }
        InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        JSONObject result = stream == null ? new JSONObject() : new JSONObject(read(stream));
        if (code != 200) {
            String note = result.optString("note", "");
            throw new Exception(code == 401
                    ? "电脑连接凭据不匹配"
                    : (note.isEmpty() ? "电脑未接受请求（" + code + "）" : note));
        }
        return result;
    }

    private static String safeMessage(Throwable error) {
        String message = error == null ? "" : error.getMessage();
        if (message == null || message.trim().isEmpty()) return error == null ? "未知错误" : error.getClass().getSimpleName();
        message = message.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        return message.length() > 220 ? message.substring(0, 220) : message;
    }

    public static String read(InputStream stream) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] chunk = new byte[4096];
        int n;
        while ((n = stream.read(chunk)) != -1) {
            if (buffer.size() + n > 100000) throw new Exception("响应过长");
            buffer.write(chunk, 0, n);
        }
        return buffer.toString("UTF-8");
    }
}
