package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import org.json.JSONObject;

/**
 * One logical device, multiple physical transports.
 * Prefers LAN, falls back to Tailcat, and retries safe/idempotent operations
 * through the alternate route after a transport failure.
 */
public final class ConnectionManager implements RelayTransport {
    private final Context context;
    private final PairingConfig pairing;
    private RelayTransport active;
    private String activeMode = "none";

    interface Operation {
        JSONObject run(RelayTransport transport) throws Exception;
    }

    public ConnectionManager(Context context, PairingConfig pairing) {
        if (context == null || pairing == null || !pairing.isAuto()) {
            throw new IllegalArgumentException("auto pairing required");
        }
        this.context = context.getApplicationContext();
        this.pairing = pairing;
    }

    public synchronized String activeMode() {
        return activeMode;
    }

    private RelayTransport lan() throws Exception {
        PairingConfig lan = new PairingConfig(
                pairing.host, pairing.port, pairing.token, pairing.fingerprint);
        // Local routes should prove themselves quickly; don't make off-LAN users
        // wait for a full socket timeout before Tailcat starts.
        return new RelayClient(context, lan, 1200, 3500);
    }

    private RelayTransport tailcat() throws Exception {
        PairingConfig remote = new PairingConfig(
                pairing.host, pairing.port, pairing.token, pairing.fingerprint,
                PairingConfig.TRANSPORT_TAILCAT, pairing.tailcatAddress, pairing.deviceId);
        return new RelayClient(context, remote, 10000, 20000);
    }

    private synchronized RelayTransport resolve() throws Exception {
        if (active != null) return active;
        Exception lanFailure = null;
        try {
            RelayTransport candidate = lan();
            JSONObject health = candidate.request(pairing.host, null);
            if (validHealth(health)) {
                active = candidate;
                activeMode = "lan";
                return active;
            }
        } catch (Exception failure) {
            lanFailure = failure;
        }

        try {
            RelayTransport candidate = tailcat();
            JSONObject health = candidate.request(pairing.host, null);
            if (!validHealth(health)) throw new Exception("跨网络接收端版本不兼容");
            active = candidate;
            activeMode = "tailcat";
            return active;
        } catch (Exception remoteFailure) {
            String lanNote = lanFailure == null ? "LAN unavailable" : safe(lanFailure);
            throw new Exception("自动连接失败；本地连接：" + lanNote
                    + "；跨网络连接：" + safe(remoteFailure), remoteFailure);
        }
    }

    private JSONObject invoke(Operation op, boolean safeRetry) throws Exception {
        RelayTransport first = resolve();
        try {
            return op.run(first);
        } catch (Exception firstFailure) {
            if (!safeRetry) throw firstFailure;
            final String failedMode;
            synchronized (this) {
                failedMode = active == first ? activeMode : "unknown";
                if (active == first) {
                    active = null;
                    activeMode = "none";
                }
            }
            RelayTransport second = resolveAlternate(failedMode);
            try {
                return op.run(second);
            } catch (Exception secondFailure) {
                throw new Exception("连接已自动切换但请求仍失败：" + safe(secondFailure), secondFailure);
            }
        }
    }

    private synchronized RelayTransport resolveAlternate(String failedMode) throws Exception {
        Exception last = null;
        if (!"tailcat".equals(failedMode)) {
            try {
                RelayTransport candidate = tailcat();
                JSONObject health = candidate.request(pairing.host, null);
                if (validHealth(health)) {
                    active = candidate;
                    activeMode = "tailcat";
                    return active;
                }
            } catch (Exception failure) { last = failure; }
        }
        if (!"lan".equals(failedMode)) {
            try {
                RelayTransport candidate = lan();
                JSONObject health = candidate.request(pairing.host, null);
                if (validHealth(health)) {
                    active = candidate;
                    activeMode = "lan";
                    return active;
                }
            } catch (Exception failure) { last = failure; }
        }
        throw last == null ? new Exception("没有可用连接") : last;
    }

    private boolean validHealth(JSONObject result) {
        return result != null && result.optBoolean("ok")
                && "VoiceInput2PC".equals(result.optString("app"))
                && result.optInt("protocol") == 2;
    }

    private String safe(Throwable error) {
        String value = error == null ? "未知错误" : error.getMessage();
        if (value == null || value.trim().isEmpty()) value = error.getClass().getSimpleName();
        value = value.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        return value.length() > 160 ? value.substring(0, 160) : value;
    }

    public JSONObject request(String host, JSONObject body) throws Exception {
        return invoke(t -> t.request(pairing.host, body), true);
    }
    public JSONObject session(String host) throws Exception {
        return invoke(t -> t.session(pairing.host), true);
    }
    public JSONObject receive(String host) throws Exception {
        return invoke(t -> t.receive(pairing.host), true);
    }
    public JSONObject acknowledge(String host, String id) throws Exception {
        return invoke(t -> t.acknowledge(pairing.host, id), true);
    }
    public JSONObject fileBegin(String host, JSONObject metadata) throws Exception {
        return invoke(t -> t.fileBegin(pairing.host, metadata), true);
    }
    public JSONObject fileChunk(String host, String transferId, long offset,
                                byte[] data, int length) throws Exception {
        return invoke(t -> t.fileChunk(pairing.host, transferId, offset, data, length), true);
    }
    public JSONObject fileComplete(String host, String transferId) throws Exception {
        // A complete request moves the durable .part file. If its response is lost,
        // don't blindly repeat it through another route.
        return invoke(t -> t.fileComplete(pairing.host, transferId), false);
    }
}
