"""Read-only health/auth/pinning check; never sends input or prints credentials."""
import hashlib
import json
import os
from pathlib import Path
import ssl
from http.client import HTTPSConnection

folder = Path(os.environ['LOCALAPPDATA']) / 'VoiceInput2PC'
config = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
context = ssl.create_default_context(cafile=str(folder / 'cert.pem'))
context.check_hostname = False
for authenticated in (False, True):
    conn = HTTPSConnection('127.0.0.1', config['port'], timeout=5, context=context)
    try:
        conn.connect()
        assert hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest() == config['fingerprint']
        headers = {'Authorization': 'Bearer ' + config['token']} if authenticated else {}
        conn.request('GET', '/health', headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())
        assert response.status == (200 if authenticated else 401)
        if authenticated:
            assert data['ok'] and data['app'] == 'VoiceInput2PC' and data['protocol'] == 2
        print(json.dumps({'authenticated': authenticated, 'http_status': response.status,
                          'certificate_pin': 'PASS', 'protocol': data.get('protocol'),
                          'paused': data.get('paused')}, ensure_ascii=True))
    finally:
        conn.close()
