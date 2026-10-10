package io.github.amxooo.voiceinput2pc;

import android.test.AndroidTestCase;
import org.json.JSONArray;
import org.json.JSONObject;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.List;

/** Deterministic route selection tests; no external network or native bridge is used. */
public final class ConnectionManagerTest extends AndroidTestCase {
    private PairingConfig pairing() {
        return new PairingConfig("192.168.1.20",23337,
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "abababababababababababababababababababababababababababababababab",
                PairingConfig.TRANSPORT_AUTO,"tcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    }
    private JSONObject health() throws Exception {
        return new JSONObject().put("ok",true).put("app","VoiceInput2PC").put("protocol",2)
                .put("lan_hosts",new JSONArray().put("10.99.1.2").put("192.168.1.20"));
    }
    private RelayTransport fake(boolean fail, List<String> targets) {
        return (RelayTransport)Proxy.newProxyInstance(RelayTransport.class.getClassLoader(),
                new Class<?>[]{RelayTransport.class}, (proxy,method,args)-> {
                    targets.add((String)args[0]);
                    if(fail) throw new java.net.ConnectException("LAN refused");
                    return health();
                });
    }
    public void testLanPreferredAndWorkingEndpointPreserved() throws Exception {
        List<String> modes=new ArrayList<>(), targets=new ArrayList<>();
        ConnectionManager manager=new ConnectionManager(getContext(),pairing(),(config,connect,read)-> {
            modes.add(config.transport); return fake(false,targets);
        });
        manager.request(pairing().host,null);
        manager.request(pairing().host,null);
        assertEquals(1,modes.size());
        assertEquals(PairingConfig.TRANSPORT_LAN,modes.get(0));
        assertEquals("lan",manager.activeMode());
        assertEquals("192.168.1.20",manager.currentLanHost());
        for(String host:targets) assertEquals("192.168.1.20",host);
        assertEquals("已连接",manager.lastLanFailure());
    }
    public void testAlternateLanRecoveryPreservesReachableHostname() throws Exception {
        PairingConfig original=pairing();
        PairingConfig named=new PairingConfig("desktop.local",original.port,original.token,
                original.fingerprint,original.transport,original.tailcatAddress,original.deviceId);
        List<String> targets=new ArrayList<>();
        ConnectionManager manager=new ConnectionManager(getContext(),named,(config,connect,read)->fake(false,targets));
        java.lang.reflect.Method alternate=ConnectionManager.class.getDeclaredMethod("resolveAlternate",String.class);
        alternate.setAccessible(true); alternate.invoke(manager,"tailcat");
        manager.request(named.host,null);
        assertEquals("desktop.local",manager.currentLanHost());
        for(String host:targets) assertEquals("desktop.local",host);
    }
    public void testLanFailureFallsBackAndExposesReason() throws Exception {
        List<String> modes=new ArrayList<>(), targets=new ArrayList<>();
        ConnectionManager manager=new ConnectionManager(getContext(),pairing(),(config,connect,read)-> {
            modes.add(config.transport); return fake(PairingConfig.TRANSPORT_LAN.equals(config.transport),targets);
        });
        assertTrue(manager.request(pairing().host,null).optBoolean("ok"));
        assertEquals(PairingConfig.TRANSPORT_LAN,modes.get(0));
        assertEquals(PairingConfig.TRANSPORT_TAILCAT,modes.get(1));
        assertEquals("tailcat",manager.activeMode());
        assertTrue(manager.lastLanFailure().contains("LAN refused"));
    }
}
