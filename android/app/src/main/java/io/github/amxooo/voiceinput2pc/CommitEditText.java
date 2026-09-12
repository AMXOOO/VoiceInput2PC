package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.KeyEvent;
import android.view.inputmethod.BaseInputConnection;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.InputConnectionWrapper;
import android.view.inputmethod.TextAttribute;
import android.widget.EditText;

/** Uses the phone's own IME; observes transactions without consuming or rewriting them. */
public final class CommitEditText extends EditText {
    private Runnable observer;
    private ObservedConnection connection;
    private boolean connectionInterrupted;

    public CommitEditText(Context context) {
        super(context);
        addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {}
            public void onTextChanged(CharSequence text, int start, int before, int count) {}
            public void afterTextChanged(Editable text) { changed(); }
        });
    }
    public void setEditObserver(Runnable observer) { this.observer = observer; }
    public boolean hasComposition() {
        return (connection != null && connection.composingExpected) || BaseInputConnection.getComposingSpanStart(getText()) >= 0;
    }
    public boolean hasOpenEdit() { return connection != null && (connection.operationDepth > 0 || connection.batchDepth > 0); }
    public boolean wasConnectionInterrupted() { return connectionInterrupted; }
    private void changed() { if (observer != null) observer.run(); }

    @Override public InputConnection onCreateInputConnection(EditorInfo outAttrs) {
        InputConnection original = super.onCreateInputConnection(outAttrs);
        if (original == null) return null;
        connectionInterrupted = false;
        connection = new ObservedConnection(original);
        return connection;
    }
    private final class ObservedConnection extends InputConnectionWrapper {
            private int operationDepth, batchDepth;
            private boolean composingExpected;
            ObservedConnection(InputConnection original) { super(original, false); }
            private void endOperation() {
                operationDepth--;
                if (connection == this) changed();
            }
            @Override public void closeConnection() {
                boolean unfinished = composingExpected || batchDepth > 0 || operationDepth > 0
                    || (connection == this && BaseInputConnection.getComposingSpanStart(getText()) >= 0);
                operationDepth++;
                if (connection == this && unfinished) connectionInterrupted = true;
                try { super.closeConnection(); }
                finally { composingExpected = false; batchDepth = 0; endOperation(); }
            }
            @Override public boolean beginBatchEdit() {
                operationDepth++; batchDepth++;
                try {
                    boolean result = super.beginBatchEdit();
                    if (!result) batchDepth--;
                    return result;
                } finally { endOperation(); }
            }
            @Override public boolean endBatchEdit() {
                operationDepth++;
                try { return super.endBatchEdit(); }
                finally { if (batchDepth > 0) batchDepth--; endOperation(); }
            }
            @Override public boolean setComposingText(CharSequence text, int cursor) {
                operationDepth++; composingExpected = true;
                try { return super.setComposingText(text, cursor); }
                finally { endOperation(); }
            }
            @Override public boolean setComposingText(CharSequence text, int cursor, TextAttribute attribute) {
                operationDepth++; composingExpected = true;
                try { return super.setComposingText(text, cursor, attribute); }
                finally { endOperation(); }
            }
            @Override public boolean setComposingRegion(int start, int end) {
                operationDepth++; composingExpected = start != end;
                try { return super.setComposingRegion(start, end); }
                finally { endOperation(); }
            }
            @Override public boolean setComposingRegion(int start, int end, TextAttribute attribute) {
                operationDepth++; composingExpected = start != end;
                try { return super.setComposingRegion(start, end, attribute); }
                finally { endOperation(); }
            }
            @Override public boolean commitText(CharSequence text, int cursor) {
                operationDepth++;
                try { return super.commitText(text, cursor); }
                finally { composingExpected = false; endOperation(); }
            }
            @Override public boolean commitText(CharSequence text, int cursor, TextAttribute attribute) {
                operationDepth++;
                try { return super.commitText(text, cursor, attribute); }
                finally { composingExpected = false; endOperation(); }
            }
            @Override public boolean finishComposingText() {
                operationDepth++;
                try { return super.finishComposingText(); }
                finally { composingExpected = false; endOperation(); }
            }
            @Override public boolean deleteSurroundingText(int before, int after) {
                operationDepth++;
                try { return super.deleteSurroundingText(before, after); }
                finally { endOperation(); }
            }
            @Override public boolean deleteSurroundingTextInCodePoints(int before, int after) {
                operationDepth++;
                try { return super.deleteSurroundingTextInCodePoints(before, after); }
                finally { endOperation(); }
            }
            @Override public boolean sendKeyEvent(KeyEvent event) {
                operationDepth++;
                try { return super.sendKeyEvent(event); }
                finally { endOperation(); }
            }
    }
}
