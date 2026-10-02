#!/usr/bin/env python3
"""Fetch the pinned Tailcat release artifacts used by VoiceInput2PC v0.5.

Artifacts are downloaded only during development/release builds and are not
committed to this repository. The release checksum manifest is itself pinned by
SHA-256 before asset hashes are trusted.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request
import zipfile


VERSION = "0.7.0"
BASE = f"https://github.com/tailscale/tailcat/releases/download/v{VERSION}"
CHECKSUMS_NAME = "checksums.txt"
CHECKSUMS_SHA256 = "26055cb931338d77ff1731c129daf653c02ef6d68febef39cdbc1bcb610176a1"
LINUX_ARM64 = f"tailcat_{VERSION}_linux_arm64.tar.gz"
WINDOWS_AMD64 = f"tailcat_{VERSION}_windows_amd64.zip"

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_DEST = ROOT / "vendor" / "tailcat" / "windows" / "tailcat.exe"
ANDROID_DEST = ROOT / "android" / "app" / "src" / "main" / "jniLibs" / "arm64-v8a" / "libtailcat.so"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(name: str) -> bytes:
    request = urllib.request.Request(
        f"{BASE}/{name}",
        headers={"User-Agent": "VoiceInput2PC-build/0.5"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def expected_hashes() -> dict[str, str]:
    data = download(CHECKSUMS_NAME)
    if sha256(data) != CHECKSUMS_SHA256:
        raise RuntimeError("Tailcat checksum manifest hash does not match the pinned release")
    result = {}
    for raw in data.decode("utf-8").splitlines():
        parts = raw.strip().split()
        if len(parts) >= 2:
            result[parts[-1].lstrip("*")] = parts[0].lower()
    return result


def verified_asset(name: str, hashes: dict[str, str]) -> bytes:
    expected = hashes.get(name)
    if not expected:
        raise RuntimeError(f"Tailcat release manifest does not contain {name}")
    data = download(name)
    actual = sha256(data)
    if actual != expected:
        raise RuntimeError(f"Tailcat asset checksum mismatch for {name}")
    return data


def extract_windows(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        candidates = [name for name in archive.namelist()
                      if Path(name).name.lower() == "tailcat.exe"]
        if len(candidates) != 1:
            raise RuntimeError("Unexpected Tailcat Windows archive layout")
        return archive.read(candidates[0])


def extract_linux(data: bytes) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = [member for member in archive.getmembers()
                   if member.isfile() and Path(member.name).name == "tailcat"]
        if len(members) != 1:
            raise RuntimeError("Unexpected Tailcat Linux archive layout")
        stream = archive.extractfile(members[0])
        if stream is None:
            raise RuntimeError("Tailcat Linux binary could not be read")
        return stream.read()


def write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    hashes = expected_hashes()
    windows = extract_windows(verified_asset(WINDOWS_AMD64, hashes))
    android = extract_linux(verified_asset(LINUX_ARM64, hashes))
    write(WINDOWS_DEST, windows)
    write(ANDROID_DEST, android)
    print(f"Tailcat v{VERSION} prepared for Windows amd64 and Android arm64.")


if __name__ == "__main__":
    main()
