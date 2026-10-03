#!/usr/bin/env python3
"""Runtime smoke test for the embedded Tailcat executable."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from receiver.tailcat import TailcatServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--port", type=int, default=23337)
    args = parser.parse_args()

    binary = args.binary.resolve()
    if not binary.is_file():
        raise SystemExit(f"Tailcat binary not found: {binary}")

    previous = os.environ.get("VOICEINPUT2PC_TAILCAT")
    os.environ["VOICEINPUT2PC_TAILCAT"] = str(binary)
    key_path = Path(os.environ.get(
        "VOICEINPUT2PC_TEST_TAILCAT_KEY",
        str(binary.parent / "voiceinput2pc-tailcat-test.private.json")))
    server = TailcatServer(args.port, key_path)
    try:
        address = server.start(timeout=20)
        if not address.startswith("tc"):
            raise SystemExit("Tailcat runtime returned an invalid address")
        print("PASS: embedded Tailcat runtime started successfully.")
    finally:
        server.stop()
        if previous is None:
            os.environ.pop("VOICEINPUT2PC_TAILCAT", None)
        else:
            os.environ["VOICEINPUT2PC_TAILCAT"] = previous


if __name__ == "__main__":
    main()
