import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from receiver.file_transfer import (
    FileTransferError,
    FileTransferManager,
    MAX_FILE_BYTES,
)


class FileTransferManagerTests(unittest.TestCase):
    def test_resume_complete_and_integrity(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            destination = root / "downloads"
            manager = FileTransferManager(root / "state", destination)
            payload = (b"hello-file-transfer-" * 40000) + b"done"
            digest = hashlib.sha256(payload).hexdigest()
            metadata = {
                "name": "report.bin",
                "size": len(payload),
                "sha256": digest,
                "mime": "application/octet-stream",
            }

            first = manager.begin(metadata)
            self.assertEqual(0, first["offset"])
            transfer_id = first["id"]

            split = 300000
            result = manager.append(transfer_id, 0, payload[:split])
            self.assertEqual(split, result["offset"])

            resumed = manager.begin(metadata)
            self.assertEqual(split, resumed["offset"])

            mismatch = manager.append(transfer_id, 0, b"wrong")
            self.assertFalse(mismatch["ok"])
            self.assertEqual(split, mismatch["offset"])

            position = split
            while position < len(payload):
                chunk = payload[position:position + 512000]
                result = manager.append(transfer_id, position, chunk)
                position = result["offset"]

            complete = manager.complete(transfer_id)
            self.assertTrue(complete["ok"])
            self.assertEqual("complete", complete["status"])
            saved = destination / complete["name"]
            self.assertEqual(payload, saved.read_bytes())
            self.assertFalse((manager.spool / f"{transfer_id}.part").exists())

    def test_rejects_bad_names_size_and_hash(self):
        with tempfile.TemporaryDirectory() as root:
            manager = FileTransferManager(Path(root) / "state", Path(root) / "dest")
            digest = hashlib.sha256(b"x").hexdigest()
            bad = [
                {"name": "../x.txt", "size": 1, "sha256": digest, "mime": "text/plain"},
                {"name": "CON.txt", "size": 1, "sha256": digest, "mime": "text/plain"},
                {"name": "bad?.txt", "size": 1, "sha256": digest, "mime": "text/plain"},
                {"name": "x.txt", "size": MAX_FILE_BYTES + 1, "sha256": digest, "mime": "text/plain"},
                {"name": "x.txt", "size": 1, "sha256": "bad", "mime": "text/plain"},
            ]
            for value in bad:
                with self.subTest(value=value):
                    with self.assertRaises(FileTransferError):
                        manager.begin(value)

    def test_complete_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            manager = FileTransferManager(root / "state", root / "dest")
            expected = hashlib.sha256(b"right").hexdigest()
            metadata = {
                "name": "x.bin",
                "size": 5,
                "sha256": expected,
                "mime": "application/octet-stream",
            }
            started = manager.begin(metadata)
            manager.append(started["id"], 0, b"wrong")
            with self.assertRaises(FileTransferError):
                manager.complete(started["id"])
            self.assertTrue((manager.spool / f"{started['id']}.part").exists())


if __name__ == "__main__":
    unittest.main()
