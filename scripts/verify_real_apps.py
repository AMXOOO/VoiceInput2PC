"""Send only to an explicitly identified, already-focused disposable test document.

UI selection and final visible-text verification are performed independently.
This script never activates a window or mutates the clipboard.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import uuid
from http.client import HTTPSConnection

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receiver.win_input import capture_target, user32


def request(path, body=None):
    folder = Path(os.environ['LOCALAPPDATA']) / 'VoiceInput2PC'
    config = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
    context = ssl.create_default_context(cafile=str(folder / 'cert.pem'))
    context.check_hostname = False
    conn = HTTPSConnection('127.0.0.1', config['port'], timeout=10, context=context)
    try:
        conn.connect()
        assert hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest() == config['fingerprint']
        conn.request('GET' if body is None else 'POST', path,
                     None if body is None else json.dumps(body).encode(),
                     {'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json'})
        response = conn.getresponse()
        result = json.loads(response.read())
        assert response.status == 200 and result.get('ok') is True, result.get('note', 'Request failed')
        return result
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expect-title', required=True)
    parser.add_argument('--expect-pid', required=True, type=int)
    parser.add_argument('--text', default='语音输入电脑验收：中文，Hello 123 👋。')
    args = parser.parse_args()
    target = capture_target()
    title = C.create_unicode_buffer(2048)
    user32.GetWindowTextW(C.c_void_p(target.window), title, len(title))
    assert target.process == args.expect_pid and title.value == args.expect_title, 'Unexpected foreground; refused'
    sequence = user32.GetClipboardSequenceNumber()
    assert request('/health')['protocol'] == 2, 'Not the current packaged receiver'
    session = request('/session', {})['session']
    assert capture_target() == target, 'Focus changed before test'
    message = {'id': 'acceptance-' + uuid.uuid4().hex, 'text': args.text, 'session': session}
    first = request('/text', message)
    repeat = request('/text', message)
    assert first['status'] == repeat['status'] == 'inserted', first['note']
    assert sequence == user32.GetClipboardSequenceNumber(), 'Clipboard unexpectedly changed'
    print(json.dumps({'dispatch': 'PASS', 'duplicate_receipt': 'PASS', 'clipboard_unchanged': True,
                      'sample': args.text, 'pid': target.process,
                      'visible_text_verification': 'required independently'}, ensure_ascii=True))


if __name__ == '__main__':
    main()
