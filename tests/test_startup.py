import unittest
import queue
import sqlite3
import tempfile
from pathlib import Path
import receiver_app


class StartupMessageTests(unittest.TestCase):
    def test_unreadable_history_returns_error_not_exception(self):
        from receiver.core import Relay
        with tempfile.TemporaryDirectory() as folder:
            relay = Relay(Path(folder) / 'db', lambda text: None)
            relay.database = str(Path(folder) / 'missing' / 'db')
            rows, error = receiver_app.read_history(relay)
            self.assertIsNone(rows)
            self.assertIn('历史', error)

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
