#!/usr/bin/env python3
"""Fetch the pinned Tailcat Windows runtime used by VoiceInput2PC v0.5.

Android no longer embeds the Tailcat CLI. Android uses an in-process Go bridge
built from the Tailcat Go library. This script only prepares the Windows
runtime and also deletes any stale Android CLI artifact left by older builds.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile


VERSION = "0.7.0"
BASE = f"https://github.com/tailscale/tailcat/releases/download/v{VERSION}"
CHECKSUMS_NAME = "checksums.txt"
CHECKSUMS_SHA256 = "26055cb931338d77ff1731c129daf653c02ef6d68febef39cdbc1bcb610176a1"
WINDOWS_AMD64 = f"tailcat_{VERSION}_windows_amd64.zip"

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_DEST = ROOT / "vendor" / "tailcat" / "windows" / "tailcat.exe"
LEGACY_ANDROID_DEST = (
    ROOT / "android" / "app" / "src" / "main" / "jniLibs" / "arm64-v8a" / "libtailcat.so"
)


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
        candidates = [
            name for name in archive.namelist()
            if Path(name).name.lower() == "tailcat.exe"
        ]
        if len(candidates) != 1:
            raise RuntimeError("Unexpected Tailcat Windows archive layout")
        return archive.read(candidates[0])


def main():
    hashes = expected_hashes()
    windows = extract_windows(verified_asset(WINDOWS_AMD64, hashes))
    WINDOWS_DEST.parent.mkdir(parents=True, exist_ok=True)
    WINDOWS_DEST.write_bytes(windows)

    if LEGACY_ANDROID_DEST.exists():
        LEGACY_ANDROID_DEST.unlink()

    print(f"Tailcat v{VERSION} prepared for Windows amd64; legacy Android CLI removed.")


if __name__ == "__main__":
    main()
