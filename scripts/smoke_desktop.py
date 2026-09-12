"""Exercise HTTPS -> deduplication -> real paste ONLY into our own test window."""
import ctypes
import hashlib
import json
import os
import socket
import ssl
import sys
import tempfile
import threading
import tkinter as tk
from http.client import HTTPSConnection
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receiver.core import Relay
from receiver.http_server import make_server
from receiver.win_input import paste_text, user32

folder = Path(os.environ['LOCALAPPDATA']) / 'VoiceInput2PC'
config = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
context = ssl.create_default_context(cafile=str(folder / 'cert.pem'))
context.check_hostname = False  # Test verifies the exact certificate fingerprint below.
root = tk.Tk()
root.title('语音输入电脑 · 专用验收窗口（将自动关闭）')
root.geometry('620x240')
field = tk.Text(root, font=('Microsoft YaHei UI', 18))
field.pack(fill='both', expand=True)
root.update()
user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.GetAncestor.restype = ctypes.c_void_p
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
target = user32.GetAncestor(root.winfo_id(), 2)
root.lift()
user32.SetForegroundWindow(target)
field.focus_force()
sample = '中文输入验证 🌍\n第二行：标点，数字 123。'
results = []
errors = []

def safe_paste(text):
    if user32.GetForegroundWindow() != target:
        raise RuntimeError('Test window is not foreground; refusing to type elsewhere')
    paste_text(text)

with tempfile.TemporaryDirectory() as temporary:
    relay = Relay(Path(temporary) / 'messages.db', safe_paste)
    server = make_server(('127.0.0.1', 0), relay, config['token'], folder / 'cert.pem', folder / 'key.pem')
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def send():
        try:
            # A stalled TLS handshake must not block other connections.
            with socket.create_connection(('127.0.0.1', server.server_port), timeout=3):
                for _ in range(2):
                    conn = HTTPSConnection('127.0.0.1', server.server_port, timeout=3, context=context)
                    conn.connect()
                    fingerprint = hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
                    assert fingerprint == config['fingerprint'], 'Certificate pin mismatch'
                    conn.request('POST', '/text', json.dumps({'id': 'smoke-desktop', 'text': sample}).encode(),
                                 {'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json'})
                    response = conn.getresponse()
                    result = json.loads(response.read())
                    conn.close()
                    assert response.status == 200 and result['status'] == 'inserted', result['note']
                    results.append(result['status'])
        except Exception as exc:
            errors.append(str(exc))

    root.after(700, lambda: threading.Thread(target=send, daemon=True).start())

    def finish():
        try:
            assert not errors, errors
            assert len(results) == 2, 'Two replies were not received'
            actual = field.get('1.0', 'end-1c').replace('\r\n', '\n')
            assert actual == sample, 'Visible text did not match one exact copy of the sample'
            print('PASS: pinned HTTPS, idle TLS isolation, Chinese/emoji/multiline actual paste, retry typed only once.')
        except Exception as exc:
            errors.append(str(exc))
            print('FAIL:', str(exc))
        finally:
            root.destroy()

    root.after(5000, finish)
    root.mainloop()
    server.shutdown()
    server.server_close()
    worker.join()
sys.exit(1 if errors else 0)
