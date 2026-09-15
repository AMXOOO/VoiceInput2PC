import unittest
import queue
import sqlite3
import tempfile
from pathlib import Path
import receiver_app


class StartupMessageTests(unittest.TestCase):
    def test_manual_launch_is_visible_and_only_background_launch_stays_hidden(self):
        self.assertTrue(receiver_app.should_show_main_window())
        self.assertTrue(receiver_app.should_show_main_window(show=True))
        self.assertTrue(receiver_app.should_show_main_window(background=True, first_setup=True))
        self.assertFalse(receiver_app.should_show_main_window(background=True))

    def test_second_launch_prefers_visible_workflow_dialog_then_restores_it(self):
        class FakeUser32:
            def __init__(self):
                self.lookups = []
                self.shown = []
                self.foreground = []

            def FindWindowW(self, _class_name, title):
                self.lookups.append(title)
                return 101 if title == receiver_app.FIRST_RUN_TITLE else 0

            def ShowWindow(self, window, command):
                self.shown.append((window, command))
                return True

            def SetForegroundWindow(self, window):
                self.foreground.append(window)
                return True

        user32 = FakeUser32()
        self.assertTrue(receiver_app.activate_existing_window(user32))
        self.assertEqual([receiver_app.FIRST_RUN_TITLE], user32.lookups)
        self.assertEqual([(101, receiver_app.SW_RESTORE)], user32.shown)
        self.assertEqual([101], user32.foreground)

    def test_second_launch_reports_when_no_receiver_window_exists(self):
        class FakeUser32:
            def FindWindowW(self, _class_name, _title):
                return 0

        self.assertFalse(receiver_app.activate_existing_window(FakeUser32()))

    def test_unreadable_history_returns_error_not_exception(self):
        from receiver.core import Relay
        with tempfile.TemporaryDirectory() as folder:
            relay = Relay(Path(folder) / 'db', lambda text: None)
            relay.database = str(Path(folder) / 'missing' / 'db')
            rows, error = receiver_app.read_history(relay)
            self.assertIsNone(rows)
            self.assertIn('历史', error)

    def test_clipboard_text_is_queued_only_after_valid_explicit_action(self):
        from receiver.core import Relay
        with tempfile.TemporaryDirectory() as folder:
            relay = Relay(Path(folder) / 'db', lambda text: None)
            ok, note = receiver_app.queue_clipboard_for_phone(
                relay, lambda: 'Word 里的文字🙂\n第二行')
            self.assertTrue(ok)
            self.assertIn('手机', note)
            waiting = relay.phone_outbox()
            self.assertEqual('Word 里的文字🙂\n第二行', waiting['text'])
            original_id = waiting['id']

            invalid_readers = [
                lambda: '',
                lambda: '   \n',
                lambda: 'x' * 20001,
                lambda: '坏\x00文字',
                lambda: (_ for _ in ()).throw(receiver_app.tk.TclError('no text')),
            ]
            for reader in invalid_readers:
                ok, note = receiver_app.queue_clipboard_for_phone(relay, reader)
                self.assertFalse(ok)
                self.assertTrue(note)
                self.assertEqual(original_id, relay.phone_outbox()['id'])

            class UnwritableRelay:
                def queue_for_phone(self, _text):
                    raise sqlite3.OperationalError('database unavailable')

            ok, note = receiver_app.queue_clipboard_for_phone(
                UnwritableRelay(), lambda: '仍然不要泄露正文')
            self.assertFalse(ok)
            self.assertIn('保存', note)
            self.assertNotIn('仍然不要泄露正文', note)

    def test_ui_poll_recovers_after_error_and_stops_scheduling_after_exit(self):
        commands = queue.Queue()
        commands.put('show')
        commands.put('pause')
        commands.put('exit')
        handled, scheduled, errors = [], [], []
        def handle(command):
            handled.append(command)
            if command == 'show':
                raise sqlite3.OperationalError('database unavailable')
            return command != 'exit'
        receiver_app.pump_commands(commands, handle, lambda: scheduled.append(True), errors.append)
        self.assertEqual(['show'], handled)
        self.assertEqual(1, len(errors))
        self.assertEqual([True], scheduled)
        receiver_app.pump_commands(commands, handle, lambda: scheduled.append(True), errors.append)
        self.assertEqual(['show', 'pause', 'exit'], handled)
        self.assertEqual([True], scheduled)

    def test_missing_file_identifies_configuration_location(self):
        formatter = getattr(receiver_app, 'startup_error_message', None)
        self.assertTrue(callable(formatter), 'Startup failures need specific, actionable error details')
        error = FileNotFoundError(2, 'missing', 'C:/example/VoiceInput2PC/config.json')
        result = formatter(error, '读取配置', Path('C:/example/VoiceInput2PC'), None)
        self.assertIn('读取配置', result)
        self.assertIn('config.json', result)
        self.assertNotIn('端口被占用', result)

    def test_bind_failure_identifies_port_without_claiming_configuration_missing(self):
        formatter = getattr(receiver_app, 'startup_error_message', None)
        self.assertTrue(callable(formatter), 'Startup failures need specific, actionable error details')
        error = OSError(10013, 'bind denied')
        result = formatter(error, '启动监听', Path('C:/example/VoiceInput2PC'), 23337)
        self.assertIn('23337', result)
        self.assertIn('10013', result)
        self.assertIn('启动监听', result)
