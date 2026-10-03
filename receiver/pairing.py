"""Versioned pairing data shared by provisioning and the Windows UI."""

from __future__ import annotations

import base64
import binascii
import datetime
from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
from urllib.parse import parse_qs, urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


PAIRING_SCHEME = 'voiceinput2pc'
PAIRING_HOST = 'pair'
MAX_URI_LENGTH = 8192
_HOST = re.compile(r'[A-Za-z0-9.-]+\Z')
_TOKEN = re.compile(r'[A-Za-z0-9_-]{32,128}\Z')
_FINGERPRINT = re.compile(r'[0-9a-f]{64}\Z')
_TAILCAT_ADDRESS = re.compile(r'tc[A-Za-z0-9_-]{20,4094}\Z')
DEFAULT_PORT = 23337
TRANSPORT_LAN = 'lan_https'
TRANSPORT_TAILCAT = 'tailcat'
TRANSPORT_AUTO = 'auto'
_TAILSCALE_RANGE = ipaddress.ip_network('100.64.0.0/10')


@dataclass(frozen=True)
class Pairing:
    host: str
    port: int
    token: str = field(repr=False)
    fingerprint: str = field(repr=False)
    transport: str = TRANSPORT_LAN
    tailcat_address: str = field(default='', repr=False)
    device_id: str = ''
    device_name: str = ''


def validate_pairing(value: Pairing) -> Pairing:
    if not isinstance(value.host, str) or validate_host(value.host) != value.host:
        raise ValueError('invalid host')
    if not isinstance(value.port, int) or isinstance(value.port, bool) or not 1 <= value.port <= 65535:
        raise ValueError('invalid port')
    if not isinstance(value.token, str) or not _TOKEN.fullmatch(value.token):
        raise ValueError('invalid token')
    if not isinstance(value.fingerprint, str) or not _FINGERPRINT.fullmatch(value.fingerprint):
        raise ValueError('invalid fingerprint')
    if value.transport not in (TRANSPORT_LAN, TRANSPORT_TAILCAT, TRANSPORT_AUTO):
        raise ValueError('invalid transport')
    address = value.tailcat_address or ''
    if value.transport in (TRANSPORT_TAILCAT, TRANSPORT_AUTO):
        if not _TAILCAT_ADDRESS.fullmatch(address):
            raise ValueError('invalid tailcat address')
    elif address:
        raise ValueError('tailcat address is only valid for remote-capable transport')
    if value.device_id and not re.fullmatch(r'[0-9a-f]{32}', value.device_id):
        raise ValueError('invalid device id')
    if value.device_name and (len(value.device_name) > 80 or any(ord(ch) < 32 for ch in value.device_name)):
        raise ValueError('invalid device name')
    return value


def validate_host(raw: str) -> str:
    host = (raw or '').strip()
    try:
        address = ipaddress.ip_address(host)
        if address.version != 4:
            raise ValueError('host must be an IPv4 address or DNS hostname')
        return str(address)
    except ValueError as address_error:
        labels = host.rstrip('.').split('.')
        valid_dns = (host and len(host) <= 253 and _HOST.fullmatch(host.rstrip('.')) and all(
            1 <= len(label) <= 63
            and re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?', label)
            for label in labels))
        if not valid_dns:
            raise ValueError('host must be an IPv4 address or DNS hostname') from address_error
        return host.rstrip('.')


def validate_port(port: int) -> int:
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError('port must be between 1 and 65535')
    return port


def encode_pairing(value: Pairing) -> str:
    validate_pairing(value)
    if value.transport == TRANSPORT_AUTO:
        raw = json.dumps({
            'v': 3,
            'id': value.device_id,
            'name': value.device_name,
            'host': value.host,
            'port': value.port,
            'token': value.token,
            'fingerprint': value.fingerprint,
            'tailcat': value.tailcat_address,
        }, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    elif value.transport == TRANSPORT_TAILCAT:
        raw = (
            f'2\n{TRANSPORT_TAILCAT}\n{value.host}\n{value.port}\n'
            f'{value.token}\n{value.fingerprint}\n{value.tailcat_address}'
        ).encode('utf-8')
    else:
        # Preserve the original payload exactly so v0.4.x Android clients keep pairing over LAN.
        raw = f'1\n{value.host}\n{value.port}\n{value.token}\n{value.fingerprint}'.encode('utf-8')
    payload = base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
    return f'{PAIRING_SCHEME}://{PAIRING_HOST}?p={payload}'


def decode_pairing(uri: str) -> Pairing:
    if not isinstance(uri, str) or not uri or len(uri) > MAX_URI_LENGTH:
        raise ValueError('invalid pairing URI')
    parsed = urlparse(uri)
    if parsed.scheme != PAIRING_SCHEME or parsed.netloc != PAIRING_HOST or parsed.path not in ('', '/'):
        raise ValueError('invalid pairing URI')
    values = parse_qs(parsed.query, strict_parsing=True)
    if set(values) != {'p'} or len(values['p']) != 1:
        raise ValueError('invalid pairing URI')
    payload = values['p'][0]
    try:
        padding = '=' * (-len(payload) % 4)
        raw = base64.b64decode(payload + padding, altchars=b'-_', validate=True).decode('utf-8')
    except (binascii.Error, UnicodeError) as exc:
        raise ValueError('invalid pairing payload') from exc
    parts = raw.split('\n')
    if len(parts) == 5 and parts[0] == '1':
        return validate_pairing(Pairing(parts[1], _decode_port(parts[2]), parts[3], parts[4]))
    if len(parts) == 7 and parts[0] == '2' and parts[1] == TRANSPORT_TAILCAT:
        return validate_pairing(Pairing(
            parts[2], _decode_port(parts[3]), parts[4], parts[5],
            transport=TRANSPORT_TAILCAT, tailcat_address=parts[6]))
    raise ValueError('unsupported pairing payload')


def _decode_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError('invalid port') from exc
    if raw != str(port):
        raise ValueError('invalid port')
    return port


def _address_rank(address: ipaddress.IPv4Address) -> tuple[int, int]:
    if address in ipaddress.ip_network('192.168.0.0/16'):
        return (0, int(address))
    if address in ipaddress.ip_network('10.0.0.0/8'):
        return (1, int(address))
    if address in ipaddress.ip_network('172.16.0.0/12'):
        return (2, int(address))
    return (3, int(address))


def detect_private_addresses(candidates=None) -> list[str]:
    if candidates is None:
        try:
            candidates = [item[4][0] for item in socket.getaddrinfo(
                socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)]
        except OSError:
            candidates = []
    found = set()
    for raw in candidates:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if (address.version == 4 and not address.is_loopback and not address.is_link_local
                and (address.is_private or address in _TAILSCALE_RANGE)):
            found.add(address)
    return [str(address) for address in sorted(found, key=_address_rank)]


def _subject_alt_names(host: str):
    try:
        name = x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        name = x509.DNSName(host)
    return [name, x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]


def _atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _replace_bundle(files: dict[Path, bytes]) -> None:
    snapshots = {path: path.read_bytes() if path.exists() else None for path in files}
    replaced = []
    try:
        for path, data in files.items():
            _atomic_write(path, data)
            replaced.append(path)
    except Exception:
        for path in replaced:
            previous = snapshots[path]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, previous)
        raise


def load_pairing(folder: Path) -> Pairing:
    folder = Path(folder)
    config_path = folder / 'config.json'
    try:
        config = json.loads(config_path.read_text(encoding='utf-8'))
        device_id = config.get('device_id') or secrets.token_hex(16)
        device_name = config.get('device_name') or socket.gethostname()[:80]
        value = Pairing(
            config['host'], config['port'], config['token'], config['fingerprint'],
            device_id=device_id, device_name=device_name)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('receiver configuration is incomplete') from exc

    value = validate_pairing(value)
    if config.get('device_id') != device_id or config.get('device_name') != device_name:
        migrated = dict(config)
        migrated['device_id'] = device_id
        migrated['device_name'] = device_name
        _atomic_write(
            config_path,
            json.dumps(migrated, ensure_ascii=False, indent=2).encode('utf-8'))
    return value


def prepare_receiver(folder: Path, host: str, port: int = DEFAULT_PORT,
                     regenerate: bool = False) -> Pairing:
    folder = Path(folder)
    selected_host = validate_host(host)
    selected_port = validate_port(port)
    config_path = folder / 'config.json'
    if config_path.exists() and not regenerate:
        current = load_pairing(folder)
        if not (folder / 'cert.pem').is_file() or not (folder / 'key.pem').is_file():
            raise ValueError('existing certificate files are incomplete')
        device_id = current.device_id or secrets.token_hex(16)
        device_name = current.device_name or socket.gethostname()[:80]
        updated = Pairing(selected_host, selected_port, current.token, current.fingerprint,
                          device_id=device_id, device_name=device_name)
        data = json.dumps({
            'host': updated.host, 'port': updated.port, 'token': updated.token,
            'fingerprint': updated.fingerprint, 'device_id': device_id,
            'device_name': device_name,
        }, ensure_ascii=False, indent=2).encode('utf-8')
        _atomic_write(config_path, data)
        return updated

    preserved_device_id = ''
    preserved_device_name = ''
    if config_path.exists():
        try:
            existing = load_pairing(folder)
            preserved_device_id = existing.device_id
            preserved_device_name = existing.device_name
        except ValueError:
            pass

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'VoiceInput2PC Receiver')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(_subject_alt_names(selected_host)), critical=False)
            .sign(key, hashes.SHA256()))
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    value = Pairing(
        selected_host, selected_port, secrets.token_urlsafe(32),
        hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
        device_id=preserved_device_id or secrets.token_hex(16),
        device_name=preserved_device_name or socket.gethostname()[:80])
    config_data = json.dumps({
        'host': value.host, 'port': value.port, 'token': value.token,
        'fingerprint': value.fingerprint, 'device_id': value.device_id,
        'device_name': value.device_name,
    }, ensure_ascii=False, indent=2).encode('utf-8')
    key_data = key.private_bytes(serialization.Encoding.PEM,
                                 serialization.PrivateFormat.PKCS8,
                                 serialization.NoEncryption())
    folder.mkdir(parents=True, exist_ok=True)
    _replace_bundle({folder / 'key.pem': key_data,
                     folder / 'cert.pem': cert_pem,
                     config_path: config_data})
    return value
