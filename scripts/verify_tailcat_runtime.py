#!/usr/bin/env python3
"""Runtime smoke test for the embedded Tailcat executable."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

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
    server = TailcatServer(args.port)
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
