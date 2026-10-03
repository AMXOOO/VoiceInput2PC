package io.github.amxooo.voiceinput2pc;

import org.json.JSONObject;

/** External I/O boundary; the Activity owns durable state and response validation. */
public interface RelayTransport {
    JSONObject request(String host, JSONObject body) throws Exception;
    JSONObject session(String host) throws Exception;
    JSONObject receive(String host) throws Exception;
    JSONObject acknowledge(String host, String id) throws Exception;

    JSONObject fileBegin(String host, JSONObject metadata) throws Exception;
    JSONObject fileChunk(String host, String transferId, long offset,
                         byte[] data, int length) throws Exception;
    JSONObject fileComplete(String host, String transferId) throws Exception;
    JSONObject pendingFile(String host) throws Exception;
    JSONObject fileOutboxChunk(String host, String id, long offset) throws Exception;
    JSONObject acknowledgeFile(String host, String id, String sha256) throws Exception;
}
