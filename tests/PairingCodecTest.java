package io.github.amxooo.voiceinput2pc;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

public final class PairingCodecTest {
    private static int checks;

    private static void check(boolean value) {
        checks++;
        if (!value) throw new AssertionError("check " + checks + " failed");
    }

    private static String repeat(String value, int count) {
        StringBuilder result = new StringBuilder();
        for (int index = 0; index < count; index++) result.append(value);
        return result.toString();
    }

    private static String payload(String raw) {
        return "voiceinput2pc://pair?p=" + Base64.getUrlEncoder().withoutPadding()
                .encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    private static void invalidUri(String value) {
        try {
            PairingCodec.decode(value);
            throw new AssertionError("accepted invalid URI");
        } catch (IllegalArgumentException expected) {
            checks++;
        }
    }

    private static void invalidConfig(String host, int port, String token, String fingerprint) {
        try {
            new PairingConfig(host, port, token, fingerprint);
            throw new AssertionError("accepted invalid configuration");
        } catch (IllegalArgumentException expected) {
            checks++;
        }
    }

    public static void main(String[] args) {
        String token = repeat("A", 43);
        String fingerprint = repeat("ab", 32);
        PairingConfig config = new PairingConfig("192.168.1.20", 23337, token, fingerprint);
        String uri = PairingCodec.encode(config);
        check(PairingCodec.decode(uri).equals(config));
        check(uri.equals(payload("1\n192.168.1.20\n23337\n" + token + "\n" + fingerprint)));
        check(!config.toString().contains(token));
        check(!config.toString().contains(fingerprint));
        check(!uri.endsWith("="));

        invalidUri("");
        invalidUri("https://example.com");
        invalidUri(payload("2\npc.lan\n23337\n" + token + "\n" + fingerprint));
        invalidUri(payload("1\npc.lan\n23337\n" + token + "\n" + fingerprint + "\nextra"));
        invalidUri(payload("1\npc\u0000lan\n23337\n" + token + "\n" + fingerprint));
        invalidUri("voiceinput2pc://pair?p=bad");
        invalidUri("voiceinput2pc://pair?p=" + repeat("A", 5000));

        invalidConfig("bad host", 23337, token, fingerprint);
        invalidConfig("pc.lan", 0, token, fingerprint);
        invalidConfig("pc.lan", 65536, token, fingerprint);
        invalidConfig("pc.lan", 23337, "short", fingerprint);
        invalidConfig("pc.lan", 23337, token, "NOT-A-FINGERPRINT");

        System.out.println(checks + " pairing checks passed");
    }
}
