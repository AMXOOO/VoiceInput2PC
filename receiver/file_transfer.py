"""Resumable phone-to-Windows file transfer storage."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePath
import re
import tempfile
import threading


MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_CHUNK_BYTES = 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[0-9a-f]{32}$")
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}
_WINDOWS_BAD = set('<>:"/\\|?*')


class FileTransferError(ValueError):
    pass


def _safe_filename(raw: str) -> str:
    if not isinstance(raw, str):
        raise FileTransferError("文件名无效")
    name = raw.strip()
    if not name or len(name) > 180:
        raise FileTransferError("文件名无效")
    if name != PurePath(name).name or "/" in name or "\\" in name:
        raise FileTransferError("文件名无效")
    if name in (".", "..") or any(ord(ch) < 32 for ch in name):
        raise FileTransferError("文件名无效")
    if name.endswith((" ", ".")) or any(ch in _WINDOWS_BAD for ch in name):
        raise FileTransferError("文件名不适用于 Windows")
    stem = name.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        raise FileTransferError("文件名不适用于 Windows")
    return name


def _safe_mime(raw: str) -> str:
    if raw is None:
        return "application/octet-stream"
    if not isinstance(raw, str) or len(raw) > 120 or any(ord(ch) < 32 for ch in raw):
        raise FileTransferError("文件类型无效")
    return raw or "application/octet-stream"


def _transfer_id(name: str, size: int, digest: str) -> str:
    material = f"{name}\n{size}\n{digest}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


class FileTransferManager:
    def __init__(self, state_dir: Path, destination_dir: Path | None = None):
        self.state_dir = Path(state_dir)
        self.spool = self.state_dir / "file-transfer"
        self.destination_dir = (
            Path(destination_dir)
            if destination_dir is not None
            else Path.home() / "Downloads" / "VoiceInput2PC"
        )
        self.spool.mkdir(parents=True, exist_ok=True)
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def begin(self, data: dict) -> dict:
        if not isinstance(data, dict):
            raise FileTransferError("文件信息无效")
        if set(data) != {"name", "size", "sha256", "mime"}:
            raise FileTransferError("文件信息无效")
        name = _safe_filename(data["name"])
        size = data["size"]
        digest = data["sha256"]
        mime = _safe_mime(data["mime"])
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or size > MAX_FILE_BYTES:
            raise FileTransferError("文件大小无效")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise FileTransferError("文件摘要无效")

        transfer_id = _transfer_id(name, size, digest)
        meta_path = self._meta_path(transfer_id)
        part_path = self._part_path(transfer_id)
        done_path = self._done_path(transfer_id)
        expected = {"id": transfer_id, "name": name, "size": size, "sha256": digest, "mime": mime}

        if done_path.exists():
            done = self._load_done(transfer_id)
            if done.get("sha256") == digest and done.get("size") == size:
                return {
                    "ok": True, "id": transfer_id, "offset": size,
                    "size": size, "status": "complete",
                }

        if meta_path.exists():
            try:
                existing = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise FileTransferError("已有传输状态损坏") from exc
            if existing != expected:
                raise FileTransferError("已有传输状态冲突")
        else:
            self._atomic_json(meta_path, expected)

        if not part_path.exists():
            part_path.touch()
        offset = part_path.stat().st_size
        if offset > size:
            raise FileTransferError("已有临时文件长度异常")
        return {
            "ok": True,
            "id": transfer_id,
            "offset": offset,
            "size": size,
            "status": "ready" if offset < size else "uploaded",
        }

    def append(self, transfer_id: str, offset: int, body: bytes) -> dict:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise FileTransferError("分块偏移无效")
        if not isinstance(body, (bytes, bytearray)) or not body or len(body) > MAX_CHUNK_BYTES:
            raise FileTransferError("文件分块无效")

        with self._lock_for(transfer_id):
            meta = self._load(transfer_id)
            part = self._part_path(transfer_id)
            current = part.stat().st_size if part.exists() else 0
            if offset != current:
                return {
                    "ok": False,
                    "status": "offset_mismatch",
                    "offset": current,
                    "size": meta["size"],
                }
            if current + len(body) > meta["size"]:
                raise FileTransferError("文件分块超过声明大小")

            with part.open("ab", buffering=0) as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            new_offset = current + len(body)
            return {
                "ok": True,
                "status": "uploaded" if new_offset == meta["size"] else "receiving",
                "offset": new_offset,
                "size": meta["size"],
            }

    def complete(self, transfer_id: str) -> dict:
        with self._lock_for(transfer_id):
            done_path = self._done_path(transfer_id)
            if done_path.exists():
                done = self._load_done(transfer_id)
                return {
                    "ok": True,
                    "status": "complete",
                    "name": done["name"],
                    "size": done["size"],
                }

            meta = self._load(transfer_id)
            part = self._part_path(transfer_id)
            if not part.exists():
                raise FileTransferError("临时文件不存在")
            size = part.stat().st_size
            if size != meta["size"]:
                return {"ok": False, "status": "incomplete", "offset": size, "size": meta["size"]}

            digest = hashlib.sha256()
            with part.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != meta["sha256"]:
                raise FileTransferError("文件完整性校验失败")

            self.destination_dir.mkdir(parents=True, exist_ok=True)
            target = self._unique_target(meta["name"])
            os.replace(part, target)
            receipt = {
                "id": transfer_id,
                "name": target.name,
                "size": meta["size"],
                "sha256": meta["sha256"],
            }
            self._atomic_json(done_path, receipt)
            try:
                self._meta_path(transfer_id).unlink()
            except FileNotFoundError:
                pass
            return {
                "ok": True,
                "status": "complete",
                "name": target.name,
                "size": meta["size"],
            }

    def _load(self, transfer_id: str) -> dict:
        if not isinstance(transfer_id, str) or not _ID.fullmatch(transfer_id):
            raise FileTransferError("传输编号无效")
        try:
            data = json.loads(self._meta_path(transfer_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FileTransferError("传输不存在或状态损坏") from exc
        return data

    def _lock_for(self, transfer_id: str) -> threading.Lock:
        if not isinstance(transfer_id, str) or not _ID.fullmatch(transfer_id):
            raise FileTransferError("传输编号无效")
        with self._locks_guard:
            return self._locks.setdefault(transfer_id, threading.Lock())

    def _meta_path(self, transfer_id: str) -> Path:
        return self.spool / f"{transfer_id}.json"

    def _done_path(self, transfer_id: str) -> Path:
        return self.spool / f"{transfer_id}.done.json"

    def _load_done(self, transfer_id: str) -> dict:
        if not isinstance(transfer_id, str) or not _ID.fullmatch(transfer_id):
            raise FileTransferError("传输编号无效")
        try:
            value = json.loads(self._done_path(transfer_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FileTransferError("完成记录损坏") from exc
        if not isinstance(value, dict) or value.get("id") != transfer_id:
            raise FileTransferError("完成记录损坏")
        return value

    def _part_path(self, transfer_id: str) -> Path:
        return self.spool / f"{transfer_id}.part"

    def _unique_target(self, name: str) -> Path:
        candidate = self.destination_dir / name
        if not candidate.exists():
            return candidate
        stem, suffix = candidate.stem, candidate.suffix
        for index in range(1, 10000):
            next_path = self.destination_dir / f"{stem} ({index}){suffix}"
            if not next_path.exists():
                return next_path
        raise FileTransferError("目标目录同名文件过多")

    @staticmethod
    def _atomic_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         delete=False, prefix=path.name + ".", suffix=".tmp") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.replace(temporary, path)
