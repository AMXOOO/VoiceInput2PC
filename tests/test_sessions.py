import tempfile
import unittest
import sqlite3
from unittest.mock import patch
from pathlib import Path
from receiver.core import Relay


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'messages.db'
        self.target = (12, 13, 14)
        self.now = 100.0
        self.typed = []
        self.relay = Relay(self.path, lambda text, target: self.typed.append((text, target)),
                           target_provider=lambda: self.target, clock=lambda: self.now)

    def message(self, key='one', session=None):
        return {'id': key, 'text': '语音 👋', 'session': session}

    def test_arm_then_duplicate_inputs_once(self):
        arm = self.relay.begin_session()
        self.assertTrue(arm['ok'])
        msg = self.message(session=arm['session'])
        self.assertEqual('inserted', self.relay.accept(msg)['status'])
        self.assertEqual('inserted', self.relay.accept(msg)['status'])
        self.assertEqual([('语音 👋', self.target)], self.typed)

    def test_missing_session_never_inputs(self):
        self.assertEqual('saved', self.relay.accept(self.message())['status'])
        self.assertFalse(self.typed)

    def test_changed_focus_disarms_even_if_original_target_returns(self):
        arm = self.relay.begin_session()
        self.target = (12, 99, 14)
        self.assertEqual('saved', self.relay.accept(self.message(session=arm['session']))['status'])
        self.target = (12, 13, 14)
        self.assertEqual('saved', self.relay.accept(self.message('two', arm['session']))['status'])
        self.assertFalse(self.typed)

    def test_expiry_restart_and_new_arm_do_not_replay(self):
        arm = self.relay.begin_session()
        self.now += 121
        msg = self.message(session=arm['session'])
        self.assertEqual('saved', self.relay.accept(msg)['status'])
        new = self.relay.begin_session()
        self.assertNotEqual(new['session'], arm['session'])
        self.assertEqual('saved', self.relay.accept(msg)['status'])
        restarted = Relay(self.path, lambda *args: self.typed.append(args),
                          target_provider=lambda: self.target)
        self.assertEqual('saved', restarted.accept(self.message('two', new['session']))['status'])
        self.assertFalse(self.typed)

    def test_pause_resume_requires_fresh_arm(self):
        arm = self.relay.begin_session()
        self.relay.paused = True
        self.assertFalse(self.relay.begin_session()['ok'])
        self.relay.paused = False
        self.assertEqual('saved', self.relay.accept(self.message(session=arm['session']))['status'])
        self.assertFalse(self.typed)

    def test_new_arm_invalidates_old_and_failure_disarms(self):
        old = self.relay.begin_session()
        arm = self.relay.begin_session()
        self.assertEqual('saved', self.relay.accept(self.message('old', old['session']))['status'])
        # A delayed old session must not disarm the newly armed session.
        self.assertEqual('inserted', self.relay.accept(self.message('new', arm['session']))['status'])
        def fail(text, target):
            raise RuntimeError('部分输入，请核对')
        self.relay.injector = fail
        self.assertEqual('saved', self.relay.accept(self.message('fail', arm['session']))['status'])
        self.relay.injector = lambda *args: self.fail('must not type after uncertain result')
        self.assertEqual('saved', self.relay.accept(self.message('after', arm['session']))['status'])

    def test_activity_refreshes_expiry_and_bad_target_returns_safe_note(self):
        arm = self.relay.begin_session()
        self.now += 100
        self.assertEqual('inserted', self.relay.accept(self.message('first', arm['session']))['status'])
        self.now += 100
        self.assertEqual('inserted', self.relay.accept(self.message('second', arm['session']))['status'])
        def bad():
            raise RuntimeError('没有可用输入框')
        self.relay.target_provider = bad
        self.assertFalse(self.relay.begin_session()['ok'])

    def test_database_failure_after_dispatch_disarms_and_never_replays(self):
        arm = self.relay.begin_session()
        connect = self.relay._connect
        calls = 0
        def fail_receipt():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise sqlite3.OperationalError('disk full')
            return connect()
        message = self.message(session=arm['session'])
        with patch.object(self.relay, '_connect', side_effect=fail_receipt):
            with self.assertRaises(sqlite3.OperationalError):
                self.relay.accept(message)
        self.assertIsNone(self.relay.session)
        self.assertEqual('saved', self.relay.accept(self.message('after-disk-fail', arm['session']))['status'])
        self.relay.accept(message)
        self.assertEqual(1, len(self.typed))


if __name__ == '__main__':
    unittest.main()
