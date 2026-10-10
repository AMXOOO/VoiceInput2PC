package io.github.amxooo.voiceinput2pc;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public final class PairingCodec {
    private static final String PREFIX = "voiceinput2pc://pair?p=";
    private static final int MAX_URI_LENGTH = 8192;

    private PairingCodec() {}

    public static String encode(PairingConfig config) {
        if (config == null) throw new IllegalArgumentException("missing pairing configuration");
        final String raw;
        if (config.isAuto()) {
            raw = "3\n" + config.deviceId + "\n"
                    + config.host + "\n" + config.port + "\n"
                    + config.token + "\n" + config.fingerprint + "\n" + config.tailcatAddress;
        } else if (config.isTailcat()) {
            raw = "2\n" + PairingConfig.TRANSPORT_TAILCAT + "\n"
                    + config.host + "\n" + config.port + "\n"
                    + config.token + "\n" + config.fingerprint + "\n" + config.tailcatAddress;
        } else {
            // Keep the original v1 payload byte-for-byte compatible with v0.4.x Android clients.
            raw = "1\n" + config.host + "\n" + config.port + "\n"
                    + config.token + "\n" + config.fingerprint;
        }
        return PREFIX + Base64.getUrlEncoder().withoutPadding()
                .encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    public static PairingConfig decode(String uri) {
        if (uri == null || uri.isEmpty() || uri.length() > MAX_URI_LENGTH
                || !uri.startsWith(PREFIX)) {
            throw new IllegalArgumentException("invalid pairing URI");
        }
        String encoded = uri.substring(PREFIX.length());
        if (encoded.isEmpty() || encoded.indexOf('&') >= 0 || encoded.indexOf('#') >= 0
                || encoded.indexOf('?') >= 0) {
            throw new IllegalArgumentException("invalid pairing URI");
        }
        final byte[] bytes;
        try {
            bytes = Base64.getUrlDecoder().decode(encoded);
        } catch (IllegalArgumentException error) {
            throw new IllegalArgumentException("invalid pairing payload", error);
        }
        final String raw;
        try {
            raw = StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException error) {
            throw new IllegalArgumentException("invalid pairing payload", error);
        }
        String[] fields = raw.split("\n", -1);
        if (fields.length == 5 && "1".equals(fields[0])) {
            return new PairingConfig(fields[1], parsePort(fields[2]), fields[3], fields[4]);
        }
        if (fields.length == 7 && "2".equals(fields[0])
                && PairingConfig.TRANSPORT_TAILCAT.equals(fields[1])) {
            return new PairingConfig(fields[2], parsePort(fields[3]), fields[4], fields[5],
                    PairingConfig.TRANSPORT_TAILCAT, fields[6]);
        }
        if (fields.length == 7 && "3".equals(fields[0])) {
            return new PairingConfig(fields[2], parsePort(fields[3]), fields[4], fields[5],
                    PairingConfig.TRANSPORT_AUTO, fields[6], fields[1]);
        }
        throw new IllegalArgumentException("unsupported pairing payload");
    }

    private static int parsePort(String raw) {
        final int port;
        try {
            port = Integer.parseInt(raw);
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException("invalid port", error);
        }
        if (!Integer.toString(port).equals(raw)) {
            throw new IllegalArgumentException("invalid port");
        }
        return port;
    }
}
