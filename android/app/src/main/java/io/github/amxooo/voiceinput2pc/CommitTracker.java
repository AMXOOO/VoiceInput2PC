package io.github.amxooo.voiceinput2pc;

/** Append-only state machine. All calls belong on the Android main thread. */
public final class CommitTracker {
    public static final class Pending {
        public final String id, snapshot, text, session;
        public Pending(String id, String snapshot, String text, String session) {
            this.id = id; this.snapshot = snapshot; this.text = text; this.session = session;
        }
    }

    private String sent, draft, ready, session = "";
    private Pending pending;
    private boolean active, conflict, saved;

    public CommitTracker(String sent, String draft, Pending pending, boolean saved) {
        this.sent = sent; this.draft = draft; this.pending = pending; this.saved = saved;
        conflict = !draft.startsWith(pending == null ? sent : pending.snapshot);
        // Composition spans cannot survive process death: require a fresh explicit start.
    }

    public void observe(String text, boolean composing, boolean batching) {
        draft = text;
        String protectedPrefix = pending == null ? sent : pending.snapshot;
        if (!text.startsWith(protectedPrefix)) { conflict = true; pause(); }
        ready = composing || batching ? null : text;
    }

    public boolean start(String newSession) {
        if (pending != null || saved || conflict || newSession == null || newSession.isEmpty()) return false;
        session = newSession; active = true;
        return true;
    }
    public void pause() { active = false; session = ""; }

    public Pending prepare(String id) {
        if (!active || pending != null || conflict || saved || ready == null || !ready.startsWith(sent)) return null;
        String suffix = ready.substring(sent.length());
        if (suffix.isEmpty() || suffix.length() > 20000 || !validUnicode(suffix)) return null;
        pending = new Pending(id, ready, normalize(suffix), session);
        return pending;
    }

    /** False leaves the durable request untouched so an ambiguous response cannot lose text. */
    public boolean receipt(String id, boolean ok, String status) {
        if (pending == null || !ok || !pending.id.equals(id)
                || !("inserted".equals(status) || "saved".equals(status))) return false;
        if ("inserted".equals(status)) {
            sent = pending.snapshot;
            if (!draft.startsWith(sent)) { conflict = true; pause(); }
        } else { saved = true; pause(); }
        pending = null;
        return true;
    }

    public String unsentForReset() { return draft.startsWith(sent) ? draft.substring(sent.length()) : draft; }

    /** UI must obtain an explicit choice before resetting saved, edited, or uncertain text. */
    public void reset(String retainedDraft) {
        pause(); sent = ""; draft = retainedDraft; ready = null; pending = null; saved = false; conflict = false;
    }

    public String draft() { return draft; }
    public String sent() { return sent; }
    public Pending pending() { return pending; }
    public boolean isActive() { return active; }
    public boolean hasConflict() { return conflict; }
    public boolean isSaved() { return saved; }

    private static String normalize(String raw) {
        return raw.replace("\r\n", " ").replace('\r', ' ').replace('\n', ' ').replace('\t', ' ');
    }
    private static boolean validUnicode(String value) {
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (Character.isHighSurrogate(c)) {
                if (++i >= value.length() || !Character.isLowSurrogate(value.charAt(i))) return false;
            } else if (Character.isLowSurrogate(c)) return false;
        }
        return true;
    }
}
