package io.github.amxooo.voiceinput2pc;

public final class DraftLogicTest {
    static void check(boolean test) { if (!test) throw new AssertionError(); }
    public static void main(String[] args) {
        check(DraftLogic.suffix("", "中文 👋", false).equals("中文 👋"));
        check(DraftLogic.suffix("中文", "中文追加", false).equals("追加"));
        check(DraftLogic.suffix("中文", "中文", false).equals(""));
        check(DraftLogic.suffix("", "zhong", true) == null);
        check(DraftLogic.suffix("已发送", "修改已发送", false) == null);
        check(DraftLogic.suffix("abc", "a", false) == null);
        System.out.println("6 draft checks passed");
    }
}
