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

        String tailcatAddress = "tc" + repeat("Z", 64);
        PairingConfig tailcat = new PairingConfig(
                "192.168.1.20", 23337, token, fingerprint,
                PairingConfig.TRANSPORT_TAILCAT, tailcatAddress);
        String tailcatUri = PairingCodec.encode(tailcat);
        check(PairingCodec.decode(tailcatUri).equals(tailcat));
        check(tailcatUri.equals(payload("2\ntailcat\n192.168.1.20\n23337\n"
                + token + "\n" + fingerprint + "\n" + tailcatAddress)));
        check(!tailcat.toString().contains(tailcatAddress));
        check(tailcat.isTailcat());

        String deviceId = "1234567890abcdef1234567890abcdef";
        PairingConfig unified = new PairingConfig(
                "192.168.1.20", 23337, token, fingerprint,
                PairingConfig.TRANSPORT_AUTO, tailcatAddress, deviceId);
        String unifiedUri = PairingCodec.encode(unified);
        check(PairingCodec.decode(unifiedUri).equals(unified));
        check(unified.isAuto());
        check(unifiedUri.equals(payload("3\n" + deviceId + "\n192.168.1.20\n23337\n"
                + token + "\n" + fingerprint + "\n" + tailcatAddress)));

        invalidUri("");
        invalidUri("https://example.com");
        invalidUri(payload("2\npc.lan\n23337\n" + token + "\n" + fingerprint));
        invalidUri(payload("1\npc.lan\n23337\n" + token + "\n" + fingerprint + "\nextra"));
        invalidUri(payload("1\npc\u0000lan\n23337\n" + token + "\n" + fingerprint));
        invalidUri("voiceinput2pc://pair?p=bad");
        invalidUri("voiceinput2pc://pair?p=" + repeat("A", 9000));

        invalidConfig("bad host", 23337, token, fingerprint);
        invalidConfig("pc.lan", 0, token, fingerprint);
        invalidConfig("pc.lan", 65536, token, fingerprint);
        invalidConfig("pc.lan", 23337, "short", fingerprint);
        invalidConfig("pc.lan", 23337, token, "NOT-A-FINGERPRINT");

        try {
            new PairingConfig("pc.lan", 23337, token, fingerprint,
                    PairingConfig.TRANSPORT_TAILCAT, "bad");
            throw new AssertionError("accepted invalid Tailcat address");
        } catch (IllegalArgumentException expected) {
            checks++;
        }

        System.out.println(checks + " pairing checks passed");
    }
}
