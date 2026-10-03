package io.github.amxooo.voiceinput2pc;

import android.content.SharedPreferences;

/** Stores paired-device credentials only in Android's private application preferences. */
public final class PairingStore {
    private static final String HOST = "pair_host";
    private static final String PORT = "pair_port";
    private static final String TOKEN = "pair_token";
    private static final String FINGERPRINT = "pair_fingerprint";
    private static final String TRANSPORT = "pair_transport";
    private static final String TAILCAT_ADDRESS = "pair_tailcat_address";
    private static final String DEVICE_ID = "pair_device_id";
    private static final String DEVICE_NAME = "pair_device_name";

    private PairingStore() {}

    public static PairingConfig load(SharedPreferences preferences) {
        if (!preferences.contains(HOST) || !preferences.contains(PORT)
                || !preferences.contains(TOKEN) || !preferences.contains(FINGERPRINT)) {
            return null;
        }
        try {
            return new PairingConfig(
                    preferences.getString(HOST, null),
                    preferences.getInt(PORT, 0),
                    preferences.getString(TOKEN, null),
                    preferences.getString(FINGERPRINT, null),
                    preferences.getString(TRANSPORT, PairingConfig.TRANSPORT_LAN),
                    preferences.getString(TAILCAT_ADDRESS, ""),
                    preferences.getString(DEVICE_ID, ""),
                    preferences.getString(DEVICE_NAME, ""));
        } catch (ClassCastException | IllegalArgumentException invalid) {
            return null;
        }
    }

    public static boolean save(SharedPreferences preferences, PairingConfig value) {
        if (preferences == null || value == null) return false;
        return preferences.edit()
                .putString(HOST, value.host)
                .putInt(PORT, value.port)
                .putString(TOKEN, value.token)
                .putString(FINGERPRINT, value.fingerprint)
                .putString(TRANSPORT, value.transport)
                .putString(TAILCAT_ADDRESS, value.tailcatAddress)
                .putString(DEVICE_ID, value.deviceId)
                .putString(DEVICE_NAME, value.deviceName)
                .putString("host", value.host)
                .commit();
    }
}
