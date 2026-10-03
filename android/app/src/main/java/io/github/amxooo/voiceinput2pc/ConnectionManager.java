package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * One logical device, multiple physical transports.
 *
 * Pairing identifies the computer. LAN host and Tailcat are merely current
 * endpoints. The manager prefers LAN, fails over to Tailcat, learns refreshed
 * LAN endpoints from authenticated health responses, and periodically returns
 * to LAN when it becomes reachable again.
 */
public final class ConnectionManager implements RelayTransport {
    private static final long LAN_REPROBE_MS = 20000L;

    private final Context context;
    private final PairingConfig pairing;

    private RelayTransport active;
    private String activeMode = "none";
    private String lanHost;
    private long lastLanProbeAt;
    private boolean lanProbeInFlight;

    interface Operation {
        JSONObject run(RelayTransport transport, String targetHost) throws Exception;
    }

    private static final class Route {
        final RelayTransport transport;
        final String mode;
        final String host;

        Route(RelayTransport transport, String mode, String host) {
            this.transport = transport;
            this.mode = mode;
            this.host = host;
        }
    }

    public ConnectionManager(Context context, PairingConfig pairing) {
        if (context == null || pairing == null || !pairing.isAuto()) {
            throw new IllegalArgumentException("auto pairing required");
        }
        this.context = context.getApplicationContext();
        this.pairing = pairing;
        this.lanHost = pairing.host;
    }

    public synchronized String activeMode() {
        return activeMode;
    }

    public synchronized String currentLanHost() {
        return lanHost;
    }

    private RelayTransport lan(String host) throws Exception {
        PairingConfig lan = new PairingConfig(
                host, pairing.port, pairing.token, pairing.fingerprint,
                PairingConfig.TRANSPORT_LAN, "", pairing.deviceId);
        // LAN should fail fast so off-LAN users don't wait for a long timeout.
        return new RelayClient(context, lan, 1200, 3500);
    }

    private RelayTransport tailcat() throws Exception {
        PairingConfig remote = new PairingConfig(
                pairing.host, pairing.port, pairing.token, pairing.fingerprint,
                PairingConfig.TRANSPORT_TAILCAT, pairing.tailcatAddress, pairing.deviceId);
        return new RelayClient(context, remote, 10000, 20000);
    }

    private synchronized Route activeRoute() {
        if (active == null) return null;
        return new Route(active, activeMode,
                "lan".equals(activeMode) ? lanHost : pairing.host);
    }

    private Route resolve() throws Exception {
        Route cached = activeRoute();
        if (cached != null) return cached;

        Exception lanFailure = null;
        String hostSnapshot;
        synchronized (this) {
            hostSnapshot = lanHost;
        }

        try {
            RelayTransport candidate = lan(hostSnapshot);
            JSONObject health = candidate.request(hostSnapshot, null);
            if (validHealth(health)) {
                absorbLanHosts(health);
                synchronized (this) {
                    active = candidate;
                    activeMode = "lan";
                }
                return new Route(candidate, "lan", hostSnapshot);
            }
        } catch (Exception failure) {
            lanFailure = failure;
        }

        try {
            RelayTransport candidate = tailcat();
            JSONObject health = candidate.request(pairing.host, null);
            if (!validHealth(health)) throw new Exception("跨网络接收端版本不兼容");
            absorbLanHosts(health);
            synchronized (this) {
                active = candidate;
                activeMode = "tailcat";
                lastLanProbeAt = System.currentTimeMillis();
            }
            return new Route(candidate, "tailcat", pairing.host);
        } catch (Exception remoteFailure) {
            String lanNote = lanFailure == null ? "LAN unavailable" : safe(lanFailure);
            throw new Exception("自动连接失败；本地连接：" + lanNote
                    + "；跨网络连接：" + safe(remoteFailure), remoteFailure);
        }
    }

    private JSONObject invoke(Operation op, boolean safeRetry) throws Exception {
        maybePreferLanAgain();
        Route first = resolve();

        try {
            JSONObject result = op.run(first.transport, first.host);
            absorbLanHosts(result);
            return result;
        } catch (Exception firstFailure) {
            if (!safeRetry) throw firstFailure;

            synchronized (this) {
                if (active == first.transport) {
                    active = null;
                    activeMode = "none";
                }
            }

            final Route second;
            try {
                second = resolveAlternate(first.mode);
            } catch (Exception alternateFailure) {
                alternateFailure.addSuppressed(firstFailure);
                throw new Exception("本地与远程连接都不可用；当前路线失败："
                        + safe(firstFailure) + "；备用路线失败：" + safe(alternateFailure),
                        alternateFailure);
            }
            try {
                JSONObject result = op.run(second.transport, second.host);
                absorbLanHosts(result);
                return result;
            } catch (Exception secondFailure) {
                secondFailure.addSuppressed(firstFailure);
                throw new Exception("已切换到" + ("lan".equals(second.mode) ? "本地连接" : "远程连接")
                        + "，但请求仍失败：" + safe(secondFailure)
                        + "；原路线：" + safe(firstFailure), secondFailure);
            }
        }
    }

    private void maybePreferLanAgain() {
        final String hostSnapshot;
        synchronized (this) {
            if (!"tailcat".equals(activeMode) || lanProbeInFlight) return;
            long now = System.currentTimeMillis();
            if (now - lastLanProbeAt < LAN_REPROBE_MS) return;
            lastLanProbeAt = now;
            lanProbeInFlight = true;
            hostSnapshot = lanHost;
        }

        Thread probe = new Thread(() -> {
            try {
                RelayTransport candidate = lan(hostSnapshot);
                JSONObject health = candidate.request(hostSnapshot, null);
                if (validHealth(health)) {
                    absorbLanHosts(health);
                    synchronized (ConnectionManager.this) {
                        // Switch only if the active path is still Tailcat. A
                        // concurrent failure/recovery may already have chosen
                        // another valid route.
                        if ("tailcat".equals(activeMode)) {
                            active = candidate;
                            activeMode = "lan";
                        }
                    }
                }
            } catch (Exception ignored) {
                // Still away from the LAN; keep the working Tailcat route.
            } finally {
                synchronized (ConnectionManager.this) {
                    lanProbeInFlight = false;
                }
            }
        }, "voiceinput2pc-lan-reprobe");
        probe.setDaemon(true);
        probe.start();
    }

    private Route resolveAlternate(String failedMode) throws Exception {
        Exception last = null;

        if (!"tailcat".equals(failedMode)) {
            try {
                RelayTransport candidate = tailcat();
                JSONObject health = candidate.request(pairing.host, null);
                if (validHealth(health)) {
                    absorbLanHosts(health);
                    synchronized (this) {
                        active = candidate;
                        activeMode = "tailcat";
                        lastLanProbeAt = System.currentTimeMillis();
                    }
                    return new Route(candidate, "tailcat", pairing.host);
                }
            } catch (Exception failure) {
                last = failure;
            }
        }

        if (!"lan".equals(failedMode)) {
            String hostSnapshot;
            synchronized (this) {
                hostSnapshot = lanHost;
            }
            try {
                RelayTransport candidate = lan(hostSnapshot);
                JSONObject health = candidate.request(hostSnapshot, null);
                if (validHealth(health)) {
                    absorbLanHosts(health);
                    synchronized (this) {
                        active = candidate;
                        activeMode = "lan";
                    }
                    return new Route(candidate, "lan", hostSnapshot);
                }
            } catch (Exception failure) {
                last = failure;
            }
        }

        throw last == null ? new Exception("没有可用连接") : last;
    }

    private boolean validHealth(JSONObject result) {
        return result != null && result.optBoolean("ok")
                && "VoiceInput2PC".equals(result.optString("app"))
                && result.optInt("protocol") == 2;
    }

    private void absorbLanHosts(JSONObject result) {
        if (result == null) return;
        JSONArray values = result.optJSONArray("lan_hosts");
        if (values == null) return;

        for (int i = 0; i < values.length(); i++) {
            String candidate = values.optString(i, "");
            if (!validHost(candidate)) continue;
            synchronized (this) {
                lanHost = candidate;
            }
            return;
        }
    }

    private boolean validHost(String value) {
        if (value == null || value.isEmpty() || value.length() > 253
                || !value.matches("[A-Za-z0-9.-]+") || value.endsWith(".")) {
            return false;
        }
        // Auto-LAN discovery intentionally excludes 100.64/10 and public
        // addresses so a separately installed VPN never masquerades as the
        // preferred local path.
        if (value.matches("^10(?:\\.\\d{1,3}){3}$")) return true;
        if (value.matches("^192\\.168(?:\\.\\d{1,3}){2}$")) return true;
        if (value.matches("^172\\.(1[6-9]|2\\d|3[01])(?:\\.\\d{1,3}){2}$")) return true;
        return false;
    }

    private String safe(Throwable error) {
        String value = error == null ? "未知错误" : error.getMessage();
        if (value == null || value.trim().isEmpty()) {
            value = error == null ? "未知错误" : error.getClass().getSimpleName();
        }
        value = value.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        return value.length() > 180 ? value.substring(0, 180) : value;
    }

    public JSONObject request(String host, JSONObject body) throws Exception {
        return invoke((t, target) -> t.request(target, body), true);
    }

    public JSONObject session(String host) throws Exception {
        return invoke((t, target) -> t.session(target), true);
    }

    public JSONObject receive(String host) throws Exception {
        return invoke((t, target) -> t.receive(target), true);
    }

    public JSONObject acknowledge(String host, String id) throws Exception {
        return invoke((t, target) -> t.acknowledge(target, id), true);
    }

    public JSONObject fileBegin(String host, JSONObject metadata) throws Exception {
        return invoke((t, target) -> t.fileBegin(target, metadata), true);
    }

    public JSONObject fileChunk(String host, String transferId, long offset,
                                byte[] data, int length) throws Exception {
        return invoke((t, target) -> t.fileChunk(target, transferId, offset, data, length), true);
    }

    public JSONObject fileComplete(String host, String transferId) throws Exception {
        // Receiver completion is idempotent and persists a completion receipt.
        return invoke((t, target) -> t.fileComplete(target, transferId), true);
    }

    public JSONObject pendingFile(String host) throws Exception {
        return invoke((t, target) -> t.pendingFile(target), true);
    }

    public JSONObject fileOutboxChunk(String host, String id, long offset) throws Exception {
        return invoke((t, target) -> t.fileOutboxChunk(target, id, offset), true);
    }

    public JSONObject acknowledgeFile(String host, String id, String sha256) throws Exception {
        return invoke((t, target) -> t.acknowledgeFile(target, id, sha256), true);
    }
}
