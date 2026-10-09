package io.github.amxooo.voiceinput2pc;

import java.util.List;

public final class HidTextEncoderTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        List<HidTextEncoder.Stroke> ascii =
            HidTextEncoder.encode("Hi!", HidTextEncoder.Mode.ASCII);
        check(ascii.size()==3, "ASCII length");
        check(ascii.get(0).modifier==2 && ascii.get(0).usage==11, "H");
        check(ascii.get(1).usage==12, "i");
        check(ascii.get(2).modifier==2 && ascii.get(2).usage==30, "!");
        boolean rejected=false;
        try { HidTextEncoder.encode("你好", HidTextEncoder.Mode.ASCII); }
        catch (IllegalArgumentException expected) { rejected=true; }
        check(rejected, "ASCII rejects Chinese");
        List<HidTextEncoder.Stroke> word =
            HidTextEncoder.encode("你", HidTextEncoder.Mode.WORD_ALT_X);
        check(word.size()==5, "4f60 plus Alt+X");
        check(word.get(4).modifier==4 && word.get(4).usage==27, "Alt+X");
        List<HidTextEncoder.Stroke> gtk =
            HidTextEncoder.encode("好", HidTextEncoder.Mode.LINUX_GTK);
        check(gtk.get(0).modifier==3 && gtk.get(0).usage==24, "Ctrl+Shift+U");
        check(gtk.get(gtk.size()-1).usage==44, "GTK space commit");
        System.out.println("HidTextEncoderTest PASS");
    }
}
