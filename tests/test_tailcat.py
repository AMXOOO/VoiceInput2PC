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
                import sys
                import time
                print("# Server listening with new address: tc" + "A" * 64, flush=True)
                time.sleep(30)
            """), encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

            with mock.patch.dict(os.environ, {"VOICEINPUT2PC_TAILCAT": str(fake)}):
                server = TailcatServer(23337)
                address = server.start(timeout=3)
                self.assertEqual("tc" + "A" * 64, address)
                self.assertIsNotNone(server.process)
                server.stop()
                self.assertIsNone(server.process)


if __name__ == "__main__":
    unittest.main()
