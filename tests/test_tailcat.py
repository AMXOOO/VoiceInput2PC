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
    def test_sidecar_extracts_address_and_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / "tailcat"
            fake.write_text(textwrap.dedent("""                #!/usr/bin/env python3
                import pathlib
                import sys
                import time

                args = sys.argv[1:]
                if args and args[0] == "genkey":
                    key_arg = next((x for x in args if x.startswith("--key=")), "")
                    if not key_arg:
                        raise SystemExit(2)
                    pathlib.Path(key_arg.split("=", 1)[1]).write_text(
                        '{"fake":"private-key"}', encoding="utf-8")
                    raise SystemExit(0)

                print("# Server listening with new address: tc" + "A" * 64, flush=True)
                time.sleep(30)
            """), encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

            local = Path(folder) / "localappdata"
            with mock.patch.dict(os.environ, {
                "VOICEINPUT2PC_TAILCAT": str(fake),
                "LOCALAPPDATA": str(local),
            }):
                server = TailcatServer(23337)
                address = server.start(timeout=3)
                self.assertEqual("tc" + "A" * 64, address)
                self.assertIsNotNone(server.process)
                self.assertTrue(
                    (local / "VoiceInput2PC" / "tailcat-server.private.json").is_file())
                server.stop()
                self.assertIsNone(server.process)


if __name__ == "__main__":
    unittest.main()
