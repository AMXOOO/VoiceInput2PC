#!/usr/bin/env python3
"""Build the Android Tailcat Go bridge reproducibly without mutating the repo."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mobile" / "tailcatbridge"
OUTPUT = ROOT / "android" / "app" / "libs" / "tailcatbridge.aar"
XMOBILE = "v0.0.0-20260908204917-8b95e45f8d3e"


def run(args, *, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main():
    go = shutil.which("go")
    if not go:
        raise SystemExit("Go 1.27+ is required to build the Android Tailcat bridge.")

    with tempfile.TemporaryDirectory(prefix="voiceinput2pc-gomobile-") as folder:
        temp = Path(folder)
        module = temp / "tailcatbridge"
        shutil.copytree(SOURCE, module, ignore=shutil.ignore_patterns("go.sum"))
        bin_dir = temp / "bin"
        bin_dir.mkdir()

        env = os.environ.copy()
        env["GOBIN"] = str(bin_dir)
        run([go, "install", f"golang.org/x/mobile/cmd/gomobile@{XMOBILE}"], env=env)
        run([go, "install", f"golang.org/x/mobile/cmd/gobind@{XMOBILE}"], env=env)
        gomobile = bin_dir / ("gomobile.exe" if os.name == "nt" else "gomobile")

        # Go 1.27 requires gobind to be present in the current module's tool graph.
        # Do this only in the temporary module so tracked go.mod remains immutable.
        run([go, "get", "-tool", f"golang.org/x/mobile/cmd/gobind@{XMOBILE}"], cwd=module, env=env)
        run([str(gomobile), "init"], cwd=module, env=env)

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        run([
            str(gomobile), "bind",
            "-target=android/arm64",
            "-androidapi=26",
            "-javapkg=io.github.amxooo.voiceinput2pc",
            "-o", str(OUTPUT),
            ".",
        ], cwd=module, env=env)
        print(f"Tailcat Android Go bridge built: {OUTPUT}")


if __name__ == "__main__":
    main()
