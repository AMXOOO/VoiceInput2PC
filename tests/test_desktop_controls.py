import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import receiver_app
from receiver.first_run import PairingDialog
from receiver.pairing import Pairing


class DesktopControlsTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_qr_can_be_resized_independently_without_changing_pairing(self):
        pairing = Pairing('192.168.1.20', 23337, 'A' * 43, 'ab' * 32,
                          device_id='a' * 32)
        with patch('receiver.first_run.get_or_start', return_value=SimpleNamespace(address='tc' + 'A' * 24)):
            dialog = PairingDialog(self.root, pairing, False)
        dialog.window.withdraw()
        self.assertEqual((1, 1), dialog.window.resizable())
        self.assertTrue(hasattr(dialog, 'qr_size'), 'QR size control is missing')
        original_uri = dialog.view.uri
        dialog.qr_size.set(280)
        dialog.render()
        smaller = dialog.qr_image.width()
        dialog.qr_size.set(480)
        dialog.render()
        self.assertGreater(dialog.qr_image.width(), smaller)
        self.assertEqual(original_uri, dialog.view.uri)

    def test_lan_only_pairing_never_starts_remote_transport(self):
        pairing = Pairing('192.168.1.20', 23337, 'A' * 43, 'ab' * 32,
                          device_id='a' * 32)
        self.assertIn('remote_enabled', __import__('inspect').signature(PairingDialog).parameters)
        with patch('receiver.first_run.get_or_start') as remote:
            dialog = PairingDialog(self.root, pairing, False, remote_enabled=False)
        remote.assert_not_called()
        self.assertEqual('lan_https', dialog.pairing.transport)
        self.assertEqual('', dialog.pairing.tailcat_address)

    def test_history_divider_changes_text_area_without_resizing_outer_window(self):
        self.assertTrue(hasattr(receiver_app, 'create_history_panes'), 'Independent text divider is missing')
        panes, listing, preview = receiver_app.create_history_panes(self.root)
        panes.pack(fill='both', expand=True)
        self.root.geometry('680x600')
        self.root.deiconify()
        self.root.update()
        panes.sashpos(0, 150)
        self.root.update()
        old_height = preview.winfo_height()
        outer_size = (self.root.winfo_width(), self.root.winfo_height())
        panes.sashpos(0, 300)
        self.root.update()
        self.assertLess(preview.winfo_height(), old_height)
        self.assertEqual(outer_size, (self.root.winfo_width(), self.root.winfo_height()))


if __name__ == '__main__':
    unittest.main()
