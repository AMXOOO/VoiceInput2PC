package io.github.amxooo.voiceinput2pc;

import org.json.JSONObject;

/** External I/O boundary; the Activity owns durable state and response validation. */
public interface RelayTransport {
    JSONObject request(String host, JSONObject body) throws Exception;
    JSONObject session(String host) throws Exception;
    JSONObject receive(String host) throws Exception;
    JSONObject acknowledge(String host, String id) throws Exception;
}
