import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from receiver.core import Relay
from receiver.http_server import make_server


class ProtocolTests(unittest.TestCase):
    def test_v2_session_over_actual_http(self):
        with tempfile.TemporaryDirectory() as folder:
            typed = []
            relay = Relay(Path(folder) / 'db', lambda text, target: typed.append(text), target_provider=lambda: (1, 2, 3))
            server = make_server(('127.0.0.1', 0), relay, 'test-secret')
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                def request(path, body=None, token='test-secret'):
                    conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    conn.request('GET' if body is None else 'POST', path,
                                 None if body is None else json.dumps(body).encode(),
                                 {'Authorization': 'Bearer ' + token})
                    response = conn.getresponse()
                    result = json.loads(response.read())
                    conn.close()
                    return response.status, result
                self.assertEqual(2, request('/health')[1]['protocol'])
                self.assertEqual(401, request('/session', {}, 'wrong')[0])
                self.assertEqual(400, request('/session', {'unexpected': True})[0])
                arm = request('/session', {})[1]
                self.assertTrue(arm['ok'])
                message = {'id': 'v2', 'text': '中文\n第二句\t👋', 'session': arm['session']}
                self.assertEqual('inserted', request('/text', message)[1]['status'])
                self.assertEqual('inserted', request('/text', message)[1]['status'])
                self.assertEqual(['中文 第二句 👋'], typed)
                self.assertEqual('saved', request('/text', {'id': 'old', 'text': '旧 APK'})[1]['status'])
            finally:
                server.shutdown()
                server.server_close()
                worker.join()

    def test_auth_unicode_and_retries_over_actual_http(self):
        with tempfile.TemporaryDirectory() as folder:
            typed = []
            server = make_server(('127.0.0.1', 0), Relay(Path(folder) / 'db', typed.append), 'test-secret')
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                def post(token, payload):
                    conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    conn.request('POST', '/text', json.dumps(payload).encode(),
                                 {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                    resp = conn.getresponse()
                    data = json.loads(resp.read())
                    conn.close()
                    return resp.status, data
                message = {'id': 'wire1', 'text': '中文、emoji 🌍、\n换行'}
                self.assertEqual(401, post('wrong', message)[0])
                self.assertEqual([], typed)
                self.assertEqual('inserted', post('test-secret', message)[1]['status'])
                self.assertEqual(200, post('test-secret', message)[0])
                self.assertEqual([message['text']], typed)
                self.assertEqual(400, post('test-secret', {'id': 'wire1', 'text': '冲突'})[0])
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
