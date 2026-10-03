package io.github.amxooo.voiceinput2pc;

import java.util.Objects;
import java.util.regex.Pattern;

public final class PairingConfig {
    public static final String TRANSPORT_LAN = "lan_https";
    public static final String TRANSPORT_TAILCAT = "tailcat";
    public static final String TRANSPORT_AUTO = "auto";
    private static final Pattern DEVICE_ID = Pattern.compile("[0-9a-f]{32}");

    private static final Pattern HOST = Pattern.compile("[A-Za-z0-9.-]+");
    private static final Pattern LABEL = Pattern.compile(
            "[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?");
    private static final Pattern TOKEN = Pattern.compile("[A-Za-z0-9_-]{32,128}");
    private static final Pattern FINGERPRINT = Pattern.compile("[0-9a-f]{64}");
    private static final Pattern TAILCAT = Pattern.compile("tc[A-Za-z0-9_-]{20,4094}");

    public final String host;
    public final int port;
    public final String token;
    public final String fingerprint;
    public final String transport;
    public final String tailcatAddress;
    public final String deviceId;

    public PairingConfig(String host, int port, String token, String fingerprint) {
        this(host, port, token, fingerprint, TRANSPORT_LAN, "", "");
    }

    public PairingConfig(String host, int port, String token, String fingerprint,
                         String transport, String tailcatAddress) {
        this(host, port, token, fingerprint, transport, tailcatAddress, "");
    }

    public PairingConfig(String host, int port, String token, String fingerprint,
                         String transport, String tailcatAddress, String deviceId) {
        validateHost(host);
        if (port < 1 || port > 65535) throw new IllegalArgumentException("invalid port");
        if (token == null || !TOKEN.matcher(token).matches()) {
            throw new IllegalArgumentException("invalid token");
        }
        if (fingerprint == null || !FINGERPRINT.matcher(fingerprint).matches()) {
            throw new IllegalArgumentException("invalid fingerprint");
        }
        if (!TRANSPORT_LAN.equals(transport) && !TRANSPORT_TAILCAT.equals(transport)
                && !TRANSPORT_AUTO.equals(transport)) {
            throw new IllegalArgumentException("invalid transport");
        }
        String address = tailcatAddress == null ? "" : tailcatAddress;
        if (TRANSPORT_TAILCAT.equals(transport) || TRANSPORT_AUTO.equals(transport)) {
            if (!TAILCAT.matcher(address).matches()) {
                throw new IllegalArgumentException("invalid tailcat address");
            }
        } else if (!address.isEmpty()) {
            throw new IllegalArgumentException("tailcat address is only valid for tailcat/auto transport");
        }
        String id = deviceId == null ? "" : deviceId;
        if (TRANSPORT_AUTO.equals(transport)) {
            if (!DEVICE_ID.matcher(id).matches()) throw new IllegalArgumentException("invalid device id");
        } else if (!id.isEmpty() && !DEVICE_ID.matcher(id).matches()) {
            throw new IllegalArgumentException("invalid device id");
        }
        this.host = host;
        this.port = port;
        this.token = token;
        this.fingerprint = fingerprint;
        this.transport = transport;
        this.tailcatAddress = address;
        this.deviceId = id;
    }

    public boolean isTailcat() {
        return TRANSPORT_TAILCAT.equals(transport);
    }

    public boolean isAuto() {
        return TRANSPORT_AUTO.equals(transport);
    }

    private static void validateHost(String host) {
        if (host == null || host.isEmpty() || host.length() > 253
                || host.endsWith(".") || !HOST.matcher(host).matches()) {
            throw new IllegalArgumentException("invalid host");
        }
        String[] labels = host.split("\\.", -1);
        for (String label : labels) {
            if (label.length() > 63 || !LABEL.matcher(label).matches()) {
                throw new IllegalArgumentException("invalid host");
            }
        }
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (!(other instanceof PairingConfig)) return false;
        PairingConfig value = (PairingConfig) other;
        return port == value.port && host.equals(value.host)
                && token.equals(value.token) && fingerprint.equals(value.fingerprint)
                && transport.equals(value.transport) && tailcatAddress.equals(value.tailcatAddress)
                && deviceId.equals(value.deviceId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(host, port, token, fingerprint, transport, tailcatAddress, deviceId);
    }

    @Override
    public String toString() {
        return "PairingConfig{host='" + host + "', port=" + port
                + ", transport='" + transport
                + "', token=<redacted>, fingerprint=<redacted>, tailcatAddress=<redacted>}";
    }
}
