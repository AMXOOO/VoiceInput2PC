package io.github.amxooo.voiceinput2pc;

public final class DraftLogic {
    private DraftLogic() {}
    /** null means composition/edit conflict: do not transmit. */
    public static String suffix(String sent, String current, boolean composing) {
        if (composing || !current.startsWith(sent)) return null;
        return current.substring(sent.length());
    }
}
