import hmac
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .core import InvalidMessage
from .file_transfer import FileTransferError, MAX_CHUNK_BYTES
from urllib.parse import parse_qs, urlparse


def make_server(address, relay, token, certificate=None, private_key=None, file_manager=None):
    context = None
    if certificate and private_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(certificate), str(private_key))

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def process_request_thread(self, request, client_address):
            # Handshakes belong to individual workers, not the accept loop.
            # An idle connection cannot hold up other phones or health checks.
            if context is not None:
                request.settimeout(5)
                try:
                    request = context.wrap_socket(request, server_side=True)
                except OSError:
                    request.close()
                    return
            super().process_request_thread(request, client_address)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'VoiceInput2PC/0.6.0'

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, fmt, *args):
            pass  # No user text, credentials, or URLs in console logs.

        def reply(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            supplied = self.headers.get('Authorization', '')
            return hmac.compare_digest(supplied.encode('utf-8'), ('Bearer ' + token).encode('utf-8'))

        def do_GET(self):
            try:
                if not self.authorized():
                    self.reply(401, {'ok': False, 'note': '连接凭据不匹配'})
                elif self.path == '/health':
                    self.reply(200, {'ok': True, 'app': 'VoiceInput2PC', 'paused': relay.paused, 'protocol': 2, 'features': ['file-upload-v1'] if file_manager is not None else []})
                elif self.path == '/outbox':
                    self.reply(200, relay.phone_outbox())
                elif self.path.startswith('/file/status'):
                    if file_manager is None:
                        self.reply(404, {'ok': False})
                    else:
                        query = parse_qs(urlparse(self.path).query)
                        transfer_id = query.get('id', [''])[0]
                        meta = file_manager._load(transfer_id)
                        part = file_manager._part_path(transfer_id)
                        offset = part.stat().st_size if part.exists() else 0
                        self.reply(200, {'ok': True, 'id': transfer_id, 'offset': offset,
                                         'size': meta['size'], 'name': meta['name']})
                else:
                    self.reply(404, {'ok': False})
            except FileTransferError as exc:
                self.reply(400, {'ok': False, 'note': str(exc)})
            except (TimeoutError, BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except Exception:
                self.reply(500, {'ok': False, 'note': '接收异常，请保留草稿并重试'})

        def do_POST(self):
            if not self.authorized():
                self.reply(401, {'ok': False, 'note': '连接凭据不匹配'})
                return
            if self.path not in ('/text', '/session', '/outbox/ack', '/file/begin', '/file/chunk', '/file/complete'):
                self.reply(404, {'ok': False})
                return
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise InvalidMessage('不支持的请求格式')
                length = int(self.headers.get('Content-Length', '0'))

                if self.path == '/file/chunk':
                    if file_manager is None:
                        self.reply(404, {'ok': False})
                        return
                    if not 0 < length <= MAX_CHUNK_BYTES:
                        raise FileTransferError('文件分块长度无效')
                    transfer_id = self.headers.get('X-Transfer-Id', '')
                    try:
                        offset = int(self.headers.get('X-Transfer-Offset', '-1'))
                    except ValueError as exc:
                        raise FileTransferError('文件分块偏移无效') from exc
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise FileTransferError('文件分块不完整')
                    self.reply(200, file_manager.append(transfer_id, offset, raw))
                    return

                if not 0 < length <= 100000:
                    raise InvalidMessage('消息长度无效')
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise InvalidMessage('消息不完整')
                data = json.loads(raw.decode('utf-8'))

                if self.path == '/file/begin':
                    if file_manager is None:
                        self.reply(404, {'ok': False})
                        return
                    self.reply(200, file_manager.begin(data))
                elif self.path == '/file/complete':
                    if file_manager is None or not isinstance(data, dict) or set(data) != {'id'}:
                        raise FileTransferError('完成请求无效')
                    self.reply(200, file_manager.complete(data['id']))
                elif self.path == '/session':
                    if data != {}:
                        raise InvalidMessage('会话请求无效')
                    self.reply(200, relay.begin_session())
                elif self.path == '/outbox/ack':
                    if not isinstance(data, dict) or set(data) != {'id'}:
                        raise InvalidMessage('接收确认无效')
                    self.reply(200, relay.ack_phone_outbox(data['id']))
                else:
                    self.reply(200, relay.accept(data))
            except FileTransferError as exc:
                self.reply(400, {'ok': False, 'note': str(exc)})
            except (ValueError, UnicodeError, InvalidMessage):
                self.reply(400, {'ok': False, 'note': '消息无效，未输入'})
            except (TimeoutError, OSError):
                self.close_connection = True
            except Exception:
                self.reply(500, {'ok': False, 'note': '接收异常，请保留草稿并重试'})

    return Server(address, Handler)
