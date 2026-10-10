import os
from pathlib import Path
import stat
import tempfile
import textwrap
import unittest
import threading
import time
from unittest import mock

from receiver.tailcat import TailcatServer
from receiver import tailcat


class TailcatServerTests(unittest.TestCase):
    def test_disabling_remote_does_not_block_ui_while_startup_holds_lifecycle_lock(self):
        acquired = threading.Event()
        release = threading.Event()
        def startup():
            with tailcat._POLICY_LOCK:
                acquired.set()
                release.wait(1)
        starter = threading.Thread(target=startup)
        starter.start()
        self.assertTrue(acquired.wait(1))
        try:
            started = time.monotonic()
            shutdown = tailcat.set_remote_enabled(False)
            self.assertLess(time.monotonic() - started, 0.3)
        finally:
            release.set()
            starter.join()
            if 'shutdown' in locals() and shutdown is not None:
                shutdown.join(2)
            tailcat.set_remote_enabled(True)

    def test_disabled_remote_stops_active_server_and_blocks_background_restart(self):
        self.assertTrue(hasattr(tailcat, 'set_remote_enabled'))
        server = mock.Mock()
        with mock.patch.dict(tailcat._ACTIVE, {23337: server}, clear=True), \
             mock.patch.object(tailcat, 'TailcatServer') as factory:
            try:
                shutdown = tailcat.set_remote_enabled(False)
                if shutdown is not None:
                    shutdown.join(2)
                server.stop.assert_called_once()
                with self.assertRaises(tailcat.TailcatUnavailable):
                    tailcat.get_or_start(23337)
                factory.assert_not_called()
                self.assertEqual({}, tailcat._ACTIVE)
            finally:
                tailcat.set_remote_enabled(True)

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
