package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import org.json.JSONObject;

/**
 * One logical connection to one paired computer.
 *
 * LAN is probed first because it is faster and cheaper. If it fails, the same
 * request is retried through Tailcat. Once a path succeeds it is preferred
 * until it fails, at which point the manager fails over to the other path.
 */
public final class ConnectionManager implements RelayTransport {
    private static final String ROUTE_LAN = "lan";
    private static final String ROUTE_TAILCAT = "tailcat";

    private final String host;
    private final RelayTransport lan;
    private final RelayTransport tailcat;
    private volatile RelayTransport active;
    private volatile String activeRoute = "";

    public ConnectionManager(Context context, PairingConfig pairing) throws Exception {
        if (pairing == null || !pairing.isAuto()) {
            throw new IllegalArgumentException("自动连接需要统一配对信息");
        }
        host = pairing.host;
        // LAN failure should be discovered quickly; remote startup may legitimately take longer.
        lan = new RelayClient(context, pairing.lanOnly(), 900, 2500);
        tailcat = new RelayClient(context, pairing.tailcatOnly(), 10000, 20000);
    }

    public String activeRoute() {
        return activeRoute;
    }

    private interface Call {
        JSONObject run(RelayTransport transport) throws Exception;
    }

    private synchronized RelayTransport choose() throws Exception {
        if (active != null) return active;

        try {
            JSONObject health = lan.request(host, null);
            if (validHealth(health)) {
                active = lan;
                activeRoute = ROUTE_LAN;
                return active;
            }
        } catch (Exception ignored) {
        }

        JSONObject health = tailcat.request(host, null);
        if (!validHealth(health)) throw new Exception("电脑接收端响应无效");
        active = tailcat;
        activeRoute = ROUTE_TAILCAT;
        return active;
    }

    private JSONObject call(Call call) throws Exception {
        RelayTransport selected = choose();
        try {
            return call.run(selected);
        } catch (Exception first) {
            RelayTransport alternate;
            synchronized (this) {
                alternate = selected == lan ? tailcat : lan;
                active = null;
                activeRoute = "";
            }
            try {
                JSONObject health = alternate.request(host, null);
                if (!validHealth(health)) throw first;
                synchronized (this) {
                    active = alternate;
                    activeRoute = alternate == lan ? ROUTE_LAN : ROUTE_TAILCAT;
                }
                return call.run(alternate);
            } catch (Exception second) {
                first.addSuppressed(second);
                throw first;
            }
        }
    }

    private static boolean validHealth(JSONObject result) {
        return result != null
                && Boolean.TRUE.equals(result.opt("ok"))
                && "VoiceInput2PC".equals(result.optString("app"))
                && result.optInt("protocol") == 2;
    }

    @Override public JSONObject request(String ignoredHost, JSONObject body) throws Exception {
        return call(t -> t.request(host, body));
    }

    @Override public JSONObject session(String ignoredHost) throws Exception {
        return call(t -> t.session(host));
    }

    @Override public JSONObject receive(String ignoredHost) throws Exception {
        return call(t -> t.receive(host));
    }

    @Override public JSONObject acknowledge(String ignoredHost, String id) throws Exception {
        return call(t -> t.acknowledge(host, id));
    }

    @Override public JSONObject fileBegin(String ignoredHost, JSONObject metadata) throws Exception {
        return call(t -> t.fileBegin(host, metadata));
    }

    @Override public JSONObject fileChunk(String ignoredHost, String transferId, long offset,
                                          byte[] data, int length) throws Exception {
        return call(t -> t.fileChunk(host, transferId, offset, data, length));
    }

    @Override public JSONObject fileComplete(String ignoredHost, String transferId) throws Exception {
        return call(t -> t.fileComplete(host, transferId));
    }
}
