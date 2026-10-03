package io.github.amxooo.voiceinput2pc;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/** Stable Java facade over the generated gomobile Tailcat bridge. */
final class TailcatNativeBridge {
    private static final String[] CLASS_NAMES = {
            "io.github.amxooo.voiceinput2pc.tailcatbridge.Tailcatbridge",
            "io.github.amxooo.voiceinput2pc.Tailcatbridge"
    };

    private TailcatNativeBridge() {}

    static int startForward(String address, int remotePort) throws Exception {
        Class<?> bridge = loadBridge();
        Method method = findStart(bridge);
        try {
            Object value;
            Class<?> portType = method.getParameterTypes()[1];
            if (portType == long.class || portType == Long.class) {
                value = method.invoke(null, address, (long) remotePort);
            } else {
                value = method.invoke(null, address, remotePort);
            }
            if (!(value instanceof Number)) throw new Exception("跨网络组件返回了无效本地端口");
            int port = ((Number) value).intValue();
            if (port < 1 || port > 65535) throw new Exception("跨网络组件返回了无效本地端口");
            return port;
        } catch (InvocationTargetException error) {
            Throwable cause = error.getCause();
            String message = cause == null ? null : cause.getMessage();
            throw new Exception("跨网络通道未建立：" + safe(message), cause == null ? error : cause);
        }
    }

    static void stop() {
        try {
            Class<?> bridge = loadBridge();
            Method method = bridge.getMethod("stopForward");
            method.invoke(null);
        } catch (Exception ignored) {
        }
    }

    private static Class<?> loadBridge() throws Exception {
        for (String name : CLASS_NAMES) {
            try {
                return Class.forName(name);
            } catch (ClassNotFoundException ignored) {
            }
        }
        throw new Exception("手机安装包缺少 Tailcat Go Bridge");
    }

    private static Method findStart(Class<?> bridge) throws Exception {
        for (Method method : bridge.getMethods()) {
            if (!"startForward".equals(method.getName())) continue;
            Class<?>[] args = method.getParameterTypes();
            if (args.length == 2 && args[0] == String.class) return method;
        }
        throw new Exception("Tailcat Go Bridge 接口不兼容");
    }

    private static String safe(String raw) {
        String value = raw == null || raw.trim().isEmpty() ? "未知错误" : raw.trim();
        value = value.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        return value.length() > 300 ? value.substring(0, 300) : value;
    }
}
