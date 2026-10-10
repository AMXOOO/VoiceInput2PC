package io.github.amxooo.voiceinput2pc;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.net.InetAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.util.Collections;
import java.util.Enumeration;

/** Stable Java facade over the generated gomobile Tailcat bridge. */
final class TailcatNativeBridge {
    private static final String BRIDGE_CLASS =
            "io.github.amxooo.voiceinput2pc.tailcatbridge.Tailcatbridge";
    private static final String LISTER_CLASS =
            "io.github.amxooo.voiceinput2pc.tailcatbridge.InterfaceLister";

    private static boolean networkHooksInstalled;
    private static Object interfaceListerProxy;

    private TailcatNativeBridge() {}

    static synchronized int startForward(Context context, String address, int remotePort)
            throws Exception {
        installAndroidNetworkHooks(context);
        Class<?> bridge = Class.forName(BRIDGE_CLASS);
        Method method = findMethod(bridge, "startForward", 2);
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
            throw new Exception("跨网络通道未建立：" + safe(message),
                    cause == null ? error : cause);
        }
    }

    static void stop() {
        try {
            Class<?> bridge = Class.forName(BRIDGE_CLASS);
            findMethod(bridge, "stopForward", 0).invoke(null);
        } catch (Exception ignored) {
        }
    }

    private static void installAndroidNetworkHooks(Context context) throws Exception {
        if (networkHooksInstalled) return;
        final Class<?> bridge = Class.forName(BRIDGE_CLASS);
        final Class<?> listerType = Class.forName(LISTER_CLASS);

        InvocationHandler handler = (proxy, method, args) -> {
            if ("interfacesAsJson".equalsIgnoreCase(method.getName())) {
                return interfacesAsJson();
            }
            if ("toString".equals(method.getName())) return "VoiceInput2PCInterfaceLister";
            if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
            if ("equals".equals(method.getName())) return proxy == (args == null ? null : args[0]);
            throw new UnsupportedOperationException(method.getName());
        };
        interfaceListerProxy = Proxy.newProxyInstance(
                listerType.getClassLoader(), new Class<?>[]{listerType}, handler);
        findMethod(bridge, "setInterfaceLister", 1).invoke(null, interfaceListerProxy);

        // Default route is optional for Tailcat startup. Keep it empty here rather
        // than request ACCESS_NETWORK_STATE solely for an optimization.
        try {
            findMethod(bridge, "setDefaultRouteInterface", 1).invoke(null, "");
        } catch (Exception ignored) {
        }
        networkHooksInstalled = true;
    }

    private static String interfacesAsJson() throws Exception {
        JSONArray all = new JSONArray();
        Enumeration<NetworkInterface> enumeration = NetworkInterface.getNetworkInterfaces();
        if (enumeration == null) throw new Exception("Android 没有返回网络接口");

        for (NetworkInterface nif : Collections.list(enumeration)) {
            JSONObject item = new JSONObject();
            item.put("name", nif.getName());
            item.put("index", nif.getIndex());
            int mtu;
            try { mtu = nif.getMTU(); } catch (Exception ignored) { mtu = 1500; }
            item.put("mtu", mtu > 0 ? mtu : 1500);
            item.put("up", safeBool(() -> nif.isUp()));
            item.put("loopback", safeBool(() -> nif.isLoopback()));
            item.put("pointToPoint", safeBool(() -> nif.isPointToPoint()));
            item.put("multicast", safeBool(() -> nif.supportsMulticast()));

            boolean broadcast = false;
            JSONArray addrs = new JSONArray();
            for (InterfaceAddress ia : nif.getInterfaceAddresses()) {
                if (ia == null) continue;
                InetAddress address = ia.getAddress();
                if (address == null) continue;
                String host = address.getHostAddress();
                if (host == null || host.isEmpty()) continue;
                JSONObject addr = new JSONObject();
                addr.put("ip", host);
                addr.put("prefixLen", (int) ia.getNetworkPrefixLength());
                addrs.put(addr);
                if (ia.getBroadcast() != null) broadcast = true;
            }
            item.put("broadcast", broadcast);
            item.put("addrs", addrs);
            all.put(item);
        }
        if (all.length() == 0) throw new Exception("Android 网络接口列表为空");
        return all.toString();
    }

    private interface BoolCall { boolean get() throws Exception; }

    private static boolean safeBool(BoolCall call) {
        try { return call.get(); } catch (Exception ignored) { return false; }
    }

    private static Method findMethod(Class<?> bridge, String name, int count) throws Exception {
        for (Method method : bridge.getMethods()) {
            if (name.equalsIgnoreCase(method.getName())
                    && method.getParameterTypes().length == count) return method;
        }
        throw new Exception("Tailcat Go Bridge 接口不兼容：" + name);
    }

    private static String safe(String raw) {
        String value = raw == null || raw.trim().isEmpty() ? "未知错误" : raw.trim();
        value = value.replaceAll("tc[A-Za-z0-9_-]{20,4094}", "tc<redacted>");
        return value.length() > 300 ? value.substring(0, 300) : value;
    }
}
