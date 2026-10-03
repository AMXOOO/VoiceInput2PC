import json
import tempfile
import threading
import unittest
from unittest import mock
from http.client import HTTPConnection
from pathlib import Path
from receiver.core import Relay
from receiver.http_server import make_server
from receiver.file_transfer import FileTransferManager


class ProtocolTests(unittest.TestCase):
    def test_outbox_read_failure_returns_controlled_500(self):
        class BrokenRelay:
            paused = False

            def phone_outbox(self):
                raise OSError('private database detail')

        server = make_server(('127.0.0.1', 0), BrokenRelay(), 'test-secret')
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            conn.request('GET', '/outbox', headers={'Authorization': 'Bearer test-secret'})
            response = conn.getresponse()
            result = json.loads(response.read())
            self.assertEqual(500, response.status)
            self.assertEqual({'ok': False, 'note': '接收异常，请保留草稿并重试'}, result)
            self.assertIn('VoiceInput2PC/0.4.0', response.getheader('Server'))
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


    def test_health_returns_current_lan_hosts_only_after_auth(self):
        with tempfile.TemporaryDirectory() as folder:
            relay = Relay(Path(folder) / 'db', lambda text: None)
            with mock.patch('receiver.http_server.detect_private_addresses',
                            return_value=['192.168.1.44', '10.0.0.8']):
                server = make_server(('127.0.0.1', 0), relay, 'test-secret')
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    def get(token):
                        conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                        conn.request('GET', '/health',
                                     headers={'Authorization': 'Bearer ' + token})
                        response = conn.getresponse()
                        body = json.loads(response.read())
                        conn.close()
                        return response.status, body

                    self.assertEqual(401, get('wrong')[0])
                    status, body = get('test-secret')
                    self.assertEqual(200, status)
                    self.assertEqual(['192.168.1.44', '10.0.0.8'], body['lan_hosts'])
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join()

    def test_phone_outbox_requires_auth_and_acknowledges_exact_item(self):
        with tempfile.TemporaryDirectory() as folder:
            relay = Relay(Path(folder) / 'db', lambda text: None)
            server = make_server(('127.0.0.1', 0), relay, 'test-secret')
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                def request(method, path, body=None, token='test-secret'):
                    conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    payload = None if body is None else json.dumps(body).encode()
                    conn.request(method, path, payload, {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json',
                    })
                    response = conn.getresponse()
                    result = json.loads(response.read())
                    conn.close()
                    return response.status, result

                self.assertEqual(401, request('GET', '/outbox', token='wrong')[0])
                self.assertEqual({'ok': True, 'available': False},
                                 request('GET', '/outbox')[1])

                queued = relay.queue_for_phone('从电脑回传🙂\n第二行')
                status, waiting = request('GET', '/outbox')
                self.assertEqual(200, status)
                self.assertEqual(queued['id'], waiting['id'])
                self.assertEqual('从电脑回传🙂\n第二行', waiting['text'])
                self.assertTrue(waiting['available'])

                self.assertEqual(400, request('POST', '/outbox/ack', {'id': 'wrong-item'})[0])
                self.assertEqual(queued['id'], request('GET', '/outbox')[1]['id'])
                received = request('POST', '/outbox/ack', {'id': queued['id']})
                self.assertEqual((200, {'ok': True, 'id': queued['id'], 'status': 'received'}), received)
                self.assertEqual(received, request('POST', '/outbox/ack', {'id': queued['id']}))
                self.assertEqual({'ok': True, 'available': False}, request('GET', '/outbox')[1])
            finally:
                server.shutdown()
                server.server_close()
                worker.join()


    def test_authenticated_file_upload_protocol(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / 'downloads'
            relay = Relay(root / 'db', lambda text: None)
            files = FileTransferManager(root / 'state', destination)
            server = make_server(('127.0.0.1', 0), relay, 'test-secret',
                                 file_manager=files)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                payload = (b'abc123' * 100000) + b'end'
                digest = __import__('hashlib').sha256(payload).hexdigest()

                def request(method, path, body=b'', token='test-secret', headers=None):
                    conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    request_headers = {'Authorization': 'Bearer ' + token}
                    if headers:
                        request_headers.update(headers)
                    conn.request(method, path, body, request_headers)
                    response = conn.getresponse()
                    raw = response.read()
                    data = json.loads(raw) if raw else {}
                    conn.close()
                    return response.status, data

                metadata = json.dumps({
                    'name': 'sample.bin',
                    'size': len(payload),
                    'sha256': digest,
                    'mime': 'application/octet-stream',
                }).encode()
                self.assertEqual(401, request('POST', '/file/begin', metadata, token='wrong')[0])

                status, started = request('POST', '/file/begin', metadata)
                self.assertEqual(200, status)
                self.assertEqual(0, started['offset'])
                transfer_id = started['id']

                first = payload[:512000]
                status, accepted = request(
                    'POST', '/file/chunk', first,
                    headers={
                        'Content-Type': 'application/octet-stream',
                        'X-Transfer-Id': transfer_id,
                        'X-Transfer-Offset': '0',
                    })
                self.assertEqual(200, status)
                self.assertEqual(len(first), accepted['offset'])

                status, resumed = request('POST', '/file/begin', metadata)
                self.assertEqual(200, status)
                self.assertEqual(len(first), resumed['offset'])

                second = payload[len(first):]
                position = len(first)
                while second:
                    chunk, second = second[:512000], second[512000:]
                    status, accepted = request(
                        'POST', '/file/chunk', chunk,
                        headers={
                            'Content-Type': 'application/octet-stream',
                            'X-Transfer-Id': transfer_id,
                            'X-Transfer-Offset': str(position),
                        })
                    self.assertEqual(200, status)
                    position = accepted['offset']

                status, completed = request(
                    'POST', '/file/complete',
                    json.dumps({'id': transfer_id}).encode())
                self.assertEqual(200, status)
                self.assertEqual('complete', completed['status'])
                self.assertEqual(payload, (destination / completed['name']).read_bytes())

                health = request('GET', '/health')[1]
                self.assertIn('file-upload-v1', health['features'])
            finally:
                server.shutdown()
                server.server_close()
                worker.join()

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
