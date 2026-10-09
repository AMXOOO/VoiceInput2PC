package io.github.amxooo.voiceinput2pc;

import java.util.ArrayList;
import java.util.List;

/** Host-side Unicode input shortcuts over standard HID keyboard reports.
 * These shortcuts are NOT universal: Word Alt+X and Linux GTK Ctrl+Shift+U.
 * A host configured with US keyboard layout is assumed.
 */
public final class HidTextEncoder {
    public enum Mode { ASCII, WORD_ALT_X, LINUX_GTK }
    private HidTextEncoder() {}
    public static final class Stroke {
        public final byte modifier, usage;
        public Stroke(int modifier, int usage) { this.modifier=(byte)modifier; this.usage=(byte)usage; }
    }
    private static Stroke hexKey(char ch) {
        if (ch >= '0' && ch <= '9') return new Stroke(0,ch=='0'?39:30+ch-'1');
        if (ch >= 'a' && ch <= 'f') return new Stroke(0,4+ch-'a');
        throw new IllegalArgumentException("invalid hex digit");
    }
    public static List<Stroke> encode(String text, Mode mode) {
        if (text == null || text.isEmpty() || text.codePointCount(0,text.length()) > 500)
            throw new IllegalArgumentException("请输入1至500个字符");
        List<Stroke> out = new ArrayList<>();
        for (int i=0;i<text.length();) {
            int cp=text.codePointAt(i); i+=Character.charCount(cp);
            if (cp >= 32 && cp <= 126) {
                out.add(ascii((char)cp));
            } else {
                if (mode == Mode.ASCII)
                    throw new IllegalArgumentException("普通 HID 模式不支持中文或非 ASCII 字符");
                if (cp < 32 || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff))
                    throw new IllegalArgumentException("包含不支持的控制字符");
                String hex=Integer.toHexString(cp);
                // Word's Alt+X operates on the preceding hex digits, not Unicode HID.
                // Only supported in editors implementing this shortcut (e.g. Microsoft Word).
                if (mode == Mode.WORD_ALT_X) {
                    for (int j=0;j<hex.length();j++) out.add(hexKey(hex.charAt(j)));
                    out.add(new Stroke(4,27)); // left Alt + X
                } else if (mode == Mode.LINUX_GTK) {
                    out.add(new Stroke(3,24)); // Ctrl+Shift+U
                    for (int j=0;j<hex.length();j++) out.add(hexKey(hex.charAt(j)));
                    out.add(new Stroke(0,44)); // Space confirms GTK Unicode input
                }
            }
        }
        return out;
    }
    private static Stroke ascii(char c) {
        if(c>='a'&&c<='z') return new Stroke(0,4+c-'a');
        if(c>='A'&&c<='Z') return new Stroke(2,4+c-'A');
        if(c>='1'&&c<='9') return new Stroke(0,30+c-'1');
        if(c=='0') return new Stroke(0,39);
        String plain=" -=[]\\;',./";
        int[] plainUsage={44,45,46,47,48,49,51,52,54,55,56};
        int idx=plain.indexOf(c);
        if(idx>=0) return new Stroke(0,plainUsage[idx]);
        String shifted="!@#$%^&*()_+{}|:\"<>?";
        int[] shiftedUsage={30,31,32,33,34,35,36,37,38,39,45,46,47,48,49,51,52,54,55,56};
        idx=shifted.indexOf(c);
        if(idx>=0) return new Stroke(2,shiftedUsage[idx]);
        if(c=='`') return new Stroke(0,53);
        if(c=='~') return new Stroke(2,53);
        throw new IllegalArgumentException("字符无法编码为 HID");
    }
}
