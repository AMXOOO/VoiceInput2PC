package io.github.amxooo.voiceinput2pc;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public final class PairingCodec {
    private static final String PREFIX = "voiceinput2pc://pair?p=";
    private static final int MAX_URI_LENGTH = 4096;

    private PairingCodec() {}

    public static String encode(PairingConfig config) {
        if (config == null) throw new IllegalArgumentException("missing pairing configuration");
        String raw = "1\n" + config.host + "\n" + config.port + "\n"
                + config.token + "\n" + config.fingerprint;
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
        String[] fields = raw.split("\\n", -1);
        if (fields.length != 5 || !"1".equals(fields[0])) {
            throw new IllegalArgumentException("unsupported pairing payload");
        }
        final int port;
        try {
            port = Integer.parseInt(fields[2]);
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException("invalid port", error);
        }
        if (!Integer.toString(port).equals(fields[2])) {
            throw new IllegalArgumentException("invalid port");
        }
        return new PairingConfig(fields[1], port, fields[3], fields[4]);
    }
}
