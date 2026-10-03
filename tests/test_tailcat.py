import os
from pathlib import Path
import stat
import tempfile
import textwrap
import unittest
from unittest import mock

from receiver.tailcat import TailcatServer


class TailcatServerTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX fake executable fixture")
    def test_sidecar_uses_persistent_private_key_and_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fake = root / "tailcat"
            calls = root / "calls.txt"
            fake.write_text(textwrap.dedent(f"""                #!/usr/bin/env python3
                import pathlib
                import sys
                import time

                args = sys.argv[1:]
                with open({str(calls)!r}, "a", encoding="utf-8") as log:
                    log.write(" ".join(args) + "\\n")

                if "genkey" in args:
                    key_arg = next(a for a in args if a.startswith("--key="))
                    pathlib.Path(key_arg.split("=", 1)[1]).write_text(
                        '{{"private":"fake"}}', encoding="utf-8")
                    raise SystemExit(0)

                print("# Server listening with saved key \"voiceinput2pc\": tc" + "A" * 64, flush=True)
                time.sleep(30)
            """), encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            key = root / "state" / "tailcat-server.private.json"

            with mock.patch.dict(os.environ, {"VOICEINPUT2PC_TAILCAT": str(fake)}):
                server = TailcatServer(23337, key)
                address = server.start(timeout=3)
                self.assertEqual("tc" + "A" * 64, address)
                self.assertTrue(key.is_file())
                server.stop()

                second = TailcatServer(23337, key)
                self.assertEqual("tc" + "A" * 64, second.start(timeout=3))
                second.stop()

            lines = calls.read_text(encoding="utf-8").splitlines()
            genkeys = [line for line in lines if "genkey" in line]
            serves = [line for line in lines if "serve" in line]
            self.assertEqual(1, len(genkeys))
            self.assertEqual(2, len(serves))
            self.assertTrue(all(str(key) in line for line in serves))


if __name__ == "__main__":
    unittest.main()
