"""Durable Windows -> phone single-file outbox."""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

MAX_OUTBOX_FILE_BYTES = 200 * 1024 * 1024
CHUNK_BYTES = 512 * 1024

class FileOutboxError(ValueError):
    pass

class FileOutbox:
    def __init__(self, state_dir: Path):
        self.root = Path(state_dir) / "phone-file-outbox"
        self.root.mkdir(parents=True, exist_ok=True)

    def queue(self, source: Path) -> dict:
        source = Path(source)
        if not source.is_file():
            raise FileOutboxError("文件不存在")
        size = source.stat().st_size
        if size > MAX_OUTBOX_FILE_BYTES:
            raise FileOutboxError("文件超过 200MB")
        item_id = uuid.uuid4().hex
        stored = self.root / (item_id + ".bin")
        digest = hashlib.sha256()
        with source.open("rb") as src, stored.open("wb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                digest.update(chunk); dst.write(chunk)
            dst.flush(); os.fsync(dst.fileno())
        meta = {"id": item_id, "name": source.name, "size": size,
                "sha256": digest.hexdigest(), "mime": "application/octet-stream"}
        self._atomic_json(self.root / (item_id + ".json"), meta)
        return meta

    def pending(self) -> dict:
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (self.root / (data.get("id", "") + ".bin")).is_file():
                return {"ok": True, "file": data}
        return {"ok": True, "file": None}

    def read(self, item_id: str, offset: int, limit: int = CHUNK_BYTES) -> tuple[bytes, int]:
        if not isinstance(item_id, str) or not item_id.isalnum() or len(item_id) != 32:
            raise FileOutboxError("文件编号无效")
        path = self.root / (item_id + ".bin")
        if not path.is_file():
            raise FileOutboxError("待接收文件不存在")
        size = path.stat().st_size
        if offset < 0 or offset > size:
            raise FileOutboxError("文件偏移无效")
        limit = max(1, min(int(limit), CHUNK_BYTES))
        with path.open("rb") as stream:
            stream.seek(offset)
            data = stream.read(limit)
        return data, size

    def acknowledge(self, item_id: str, sha256: str) -> dict:
        meta_path = self.root / (item_id + ".json")
        data_path = self.root / (item_id + ".bin")
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FileOutboxError("待接收文件不存在") from exc
        if meta.get("sha256") != sha256:
            raise FileOutboxError("文件校验值不一致")
        try: data_path.unlink()
        except FileNotFoundError: pass
        try: meta_path.unlink()
        except FileNotFoundError: pass
        return {"ok": True, "status": "received", "id": item_id}

    @staticmethod
    def _atomic_json(path: Path, data: dict):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         delete=False, suffix=".tmp") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush(); os.fsync(stream.fileno()); temp = Path(stream.name)
        os.replace(temp, path)
