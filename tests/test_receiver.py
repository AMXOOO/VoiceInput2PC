import concurrent.futures
import tempfile
import unittest
from pathlib import Path

try:
    from receiver.core import Relay, InvalidMessage
except ImportError:
    Relay = None
    InvalidMessage = ValueError


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Relay, 'Receiver has not been implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'messages.db'
        self.typed = []
        self.relay = Relay(self.db, self.typed.append)

    def test_unicode_and_retry_survives_restart(self):
        msg = {'id': 'test_001', 'text': '手机语音输入，Hello 👋\n第二行。'}
        self.assertEqual('inserted', self.relay.accept(msg)['status'])
        again = Relay(self.db, self.typed.append)
        self.assertEqual('inserted', again.accept(msg)['status'])
        self.assertEqual([msg['text']], self.typed)

    def test_parallel_retry_inserts_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            out = list(pool.map(lambda _: self.relay.accept({'id': 'same_id', 'text': '同一句'}), range(20)))
        self.assertEqual(['同一句'], self.typed)
        self.assertTrue(all(x['status'] == 'inserted' for x in out))

    def test_collision_and_invalid_payload_do_not_type(self):
        self.relay.accept({'id': 'same_id', 'text': '甲'})
        with self.assertRaises(InvalidMessage):
            self.relay.accept({'id': 'same_id', 'text': '乙'})
        for data in [{}, {'id': '../bad', 'text': 'a'}, {'id': 'a', 'text': ''},
                     {'id': 'a', 'text': 'x' * 20001}, {'id': 'b', 'text': '\x00'},
                     {'id': 'c', 'text': '\ud800'}, {'id': 'z', 'text': 3}]:
            with self.assertRaises(InvalidMessage):
                self.relay.accept(data)
        self.assertEqual(['甲'], self.typed)

    def test_failure_is_saved_without_retyping(self):
        calls = []
        def failure(text):
            calls.append(text)
            raise RuntimeError('No editable foreground window')
        relay = Relay(self.db, failure)
        message = {'id': 'retry_01', 'text': '不能丢失'}
        self.assertEqual('saved', relay.accept(message)['status'])
        self.assertEqual('saved', relay.accept(message)['status'])
        self.assertEqual(['不能丢失'], calls)
        self.assertEqual('不能丢失', relay.recent()[0]['text'])

    def test_paused_saves_without_typing(self):
        self.relay.paused = True
        self.assertEqual('saved', self.relay.accept({'id': 'pause_1', 'text': '保存'})['status'])
        self.assertEqual([], self.typed)

    def test_phone_outbox_persists_and_acknowledges_idempotently(self):
        queued = self.relay.queue_for_phone('电脑文字🙂\n第二行')
        self.assertTrue(queued['ok'])
        self.assertEqual('pending', queued['status'])
        self.assertRegex(queued['id'], r'^[A-Za-z0-9_-]{1,80}$')

        restarted = Relay(self.db, self.typed.append)
        waiting = restarted.phone_outbox()
        self.assertTrue(waiting['available'])
        self.assertEqual(queued['id'], waiting['id'])
        self.assertEqual('电脑文字🙂\n第二行', waiting['text'])

        received = restarted.ack_phone_outbox(queued['id'])
        self.assertEqual({'ok': True, 'id': queued['id'], 'status': 'received'}, received)
        self.assertFalse(restarted.phone_outbox()['available'])
        self.assertEqual(received, restarted.ack_phone_outbox(queued['id']))

    def test_new_phone_outbox_replaces_old_and_stale_ack_is_safe(self):
        old = self.relay.queue_for_phone('旧文字')
        current = self.relay.queue_for_phone('新文字')
        self.assertNotEqual(old['id'], current['id'])
        with self.assertRaises(InvalidMessage):
            self.relay.ack_phone_outbox(old['id'])
        waiting = self.relay.phone_outbox()
        self.assertEqual(current['id'], waiting['id'])
        self.assertEqual('新文字', waiting['text'])

    def test_invalid_phone_outbox_text_never_replaces_waiting_text(self):
        queued = self.relay.queue_for_phone('保留这条')
        for text in ['', 'x' * 20001, '坏\x00文字', 3, None]:
            with self.assertRaises(InvalidMessage):
                self.relay.queue_for_phone(text)
        waiting = self.relay.phone_outbox()
        self.assertEqual(queued['id'], waiting['id'])
        self.assertEqual('保留这条', waiting['text'])


if __name__ == '__main__':
    unittest.main()
