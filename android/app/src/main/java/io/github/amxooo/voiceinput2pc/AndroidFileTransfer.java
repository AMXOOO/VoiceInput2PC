package io.github.amxooo.voiceinput2pc;

import android.content.ContentResolver;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;

import org.json.JSONObject;

import java.io.InputStream;
import java.security.MessageDigest;
import java.util.Locale;

/** Phone -> Windows single-file uploader with resume and SHA-256 verification. */
final class AndroidFileTransfer {
    static final long MAX_FILE_BYTES = 200L * 1024L * 1024L;
    static final int CHUNK_BYTES = 512 * 1024;

    interface Progress {
        void onProgress(long sent, long total);
    }

    static final class Metadata {
        final String name;
        final String mime;
        final long size;
        final String sha256;

        Metadata(String name, String mime, long size, String sha256) {
            this.name = name;
            this.mime = mime;
            this.size = size;
            this.sha256 = sha256;
        }

        JSONObject json() throws Exception {
            return new JSONObject()
                    .put("name", name)
                    .put("mime", mime)
                    .put("size", size)
                    .put("sha256", sha256);
        }
    }

    private AndroidFileTransfer() {}

    static Metadata inspect(ContentResolver resolver, Uri uri, Progress progress) throws Exception {
        String name = queryName(resolver, uri);
        String mime = resolver.getType(uri);
        if (mime == null || mime.trim().isEmpty()) mime = "application/octet-stream";

        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long count = 0;
        byte[] buffer = new byte[CHUNK_BYTES];
        try (InputStream stream = resolver.openInputStream(uri)) {
            if (stream == null) throw new Exception("无法读取所选文件");
            int n;
            while ((n = stream.read(buffer)) != -1) {
                count += n;
                if (count > MAX_FILE_BYTES) throw new Exception("文件超过 200MB");
                digest.update(buffer, 0, n);
                if (progress != null) progress.onProgress(count, -1);
            }
        }
        return new Metadata(name, mime, count, hex(digest.digest()));
    }

    static JSONObject upload(ContentResolver resolver, Uri uri, Metadata metadata,
                             RelayTransport client, String host, Progress progress) throws Exception {
        JSONObject begin = client.fileBegin(host, metadata.json());
        if (!begin.optBoolean("ok")) throw new Exception(begin.optString("note", "电脑未接受文件"));
        String id = begin.optString("id", "");
        long offset = begin.optLong("offset", -1);
        if (!id.matches("[0-9a-f]{32}") || offset < 0 || offset > metadata.size) {
            throw new Exception("电脑返回的续传状态无效");
        }

        if (offset < metadata.size) {
            try (InputStream stream = resolver.openInputStream(uri)) {
                if (stream == null) throw new Exception("无法重新打开所选文件");
                skipExactly(stream, offset);
                byte[] buffer = new byte[CHUNK_BYTES];
                long position = offset;
                if (progress != null) progress.onProgress(position, metadata.size);
                while (position < metadata.size) {
                    int wanted = (int) Math.min(buffer.length, metadata.size - position);
                    int n = readUpTo(stream, buffer, wanted);
                    if (n <= 0) throw new Exception("文件在上传过程中被截断");

                    JSONObject result = client.fileChunk(host, id, position, buffer, n);
                    long acknowledged = result.optLong("offset", -1);
                    if (!result.optBoolean("ok")) {
                        if ("offset_mismatch".equals(result.optString("status"))
                                && acknowledged >= 0 && acknowledged <= metadata.size) {
                            // Reopen and resume from the server's exact durable offset.
                            return upload(resolver, uri, metadata, client, host, progress);
                        }
                        throw new Exception(result.optString("note", "电脑未接受文件分块"));
                    }
                    if (acknowledged != position + n) throw new Exception("电脑返回的文件偏移不一致");
                    position = acknowledged;
                    if (progress != null) progress.onProgress(position, metadata.size);
                }
            }
        }

        JSONObject complete = client.fileComplete(host, id);
        if (!complete.optBoolean("ok") || !"complete".equals(complete.optString("status"))) {
            throw new Exception(complete.optString("note", "电脑未完成文件校验"));
        }
        return complete;
    }

    private static String queryName(ContentResolver resolver, Uri uri) throws Exception {
        try (Cursor cursor = resolver.query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) {
                    String value = cursor.getString(index);
                    if (value != null && !value.trim().isEmpty()) return value.trim();
                }
            }
        }
        String fallback = uri.getLastPathSegment();
        if (fallback == null || fallback.trim().isEmpty()) throw new Exception("无法读取文件名");
        int slash = fallback.lastIndexOf('/');
        return (slash >= 0 ? fallback.substring(slash + 1) : fallback).trim();
    }

    private static void skipExactly(InputStream stream, long bytes) throws Exception {
        long remaining = bytes;
        byte[] discard = new byte[64 * 1024];
        while (remaining > 0) {
            long skipped = stream.skip(remaining);
            if (skipped > 0) {
                remaining -= skipped;
                continue;
            }
            int n = stream.read(discard, 0, (int) Math.min(discard.length, remaining));
            if (n < 0) throw new Exception("无法定位到续传位置");
            remaining -= n;
        }
    }

    private static int readUpTo(InputStream stream, byte[] buffer, int wanted) throws Exception {
        int total = 0;
        while (total < wanted) {
            int n = stream.read(buffer, total, wanted - total);
            if (n < 0) break;
            total += n;
        }
        return total;
    }

    private static String hex(byte[] bytes) {
        StringBuilder value = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) value.append(String.format(Locale.ROOT, "%02x", b & 255));
        return value.toString();
    }
}
