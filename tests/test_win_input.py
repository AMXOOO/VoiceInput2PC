import ctypes
import unittest
from unittest.mock import patch
from receiver import win_input


class UnicodeInputTests(unittest.TestCase):
    def test_packets_are_unicode_only_and_preserve_surrogates(self):
        packets = win_input.unicode_packets('中A👋')
        self.assertEqual(8, len(packets))
        units = [0x4e2d, 65, 0xd83d, 0xdc4b]
        for i, unit in enumerate(units):
            down, up = packets[i*2], packets[i*2+1]
            self.assertEqual((1, 0, unit, 4), (down.type, down.ki.wVk, down.ki.wScan, down.ki.dwFlags))
            self.assertEqual((0, unit, 6), (up.ki.wVk, up.ki.wScan, up.ki.dwFlags))
        self.assertEqual(40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28, ctypes.sizeof(win_input.INPUT))

    def test_control_characters_never_become_enter_or_tab(self):
        for value in ('\n', '\r', '\t', '\x00', '\x7f', '\ud800'):
            with self.assertRaises(ValueError):
                win_input.unicode_packets('abc' + value)

    def test_foreground_change_or_modifier_never_calls_sendinput(self):
        with patch.object(win_input, 'capture_target', return_value=('different',)), \
             patch.object(win_input.user32, 'SendInput') as send:
            with self.assertRaises(RuntimeError):
                win_input.type_text('安全', ('expected',))
            send.assert_not_called()
        with patch.object(win_input, 'capture_target', return_value=('same',)), \
             patch.object(win_input.user32, 'GetAsyncKeyState', return_value=-32768), \
             patch.object(win_input.user32, 'SendInput') as send:
            with self.assertRaises(RuntimeError):
                win_input.type_text('安全', ('same',))
            send.assert_not_called()

    def test_dispatch_uses_no_clipboard_and_does_not_retry_partial_input(self):
        with patch.object(win_input, 'capture_target', return_value=('same',)), \
             patch.object(win_input.user32, 'GetAsyncKeyState', return_value=0), \
             patch.object(win_input.user32, 'SendInput', return_value=1) as send, \
             patch.object(win_input, 'copy_text') as clipboard:
            with self.assertRaisesRegex(RuntimeError, '核对'):
                win_input.type_text('中文', ('same',))
            self.assertEqual(1, send.call_count)
            clipboard.assert_not_called()


if __name__ == '__main__':
    unittest.main()
