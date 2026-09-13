package io.github.amxooo.voiceinput2pc;

import java.util.Objects;
import java.util.regex.Pattern;

public final class PairingConfig {
    private static final Pattern HOST = Pattern.compile("[A-Za-z0-9.-]+");
    private static final Pattern LABEL = Pattern.compile(
            "[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?");
    private static final Pattern TOKEN = Pattern.compile("[A-Za-z0-9_-]{32,128}");
    private static final Pattern FINGERPRINT = Pattern.compile("[0-9a-f]{64}");

    public final String host;
    public final int port;
    public final String token;
    public final String fingerprint;

    public PairingConfig(String host, int port, String token, String fingerprint) {
        validateHost(host);
        if (port < 1 || port > 65535) throw new IllegalArgumentException("invalid port");
        if (token == null || !TOKEN.matcher(token).matches()) {
            throw new IllegalArgumentException("invalid token");
        }
        if (fingerprint == null || !FINGERPRINT.matcher(fingerprint).matches()) {
            throw new IllegalArgumentException("invalid fingerprint");
        }
        this.host = host;
        this.port = port;
        this.token = token;
        this.fingerprint = fingerprint;
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
                && token.equals(value.token) && fingerprint.equals(value.fingerprint);
    }

    @Override
    public int hashCode() {
        return Objects.hash(host, port, token, fingerprint);
    }

    @Override
    public String toString() {
        return "PairingConfig{host='" + host + "', port=" + port
                + ", token=<redacted>, fingerprint=<redacted>}";
    }
}
