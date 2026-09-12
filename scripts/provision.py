"""Generate private receiver credentials and an Android pairing asset locally."""

import argparse
import datetime
import hashlib
import ipaddress
import json
import os
import re
import secrets
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 23337


def validate_host(raw):
    host = (raw or '').strip()
    try:
        address = ipaddress.ip_address(host)
        if address.version != 4:
            raise ValueError('host must be an IPv4 address or DNS hostname')
        return str(address)
    except ValueError as address_error:
        labels = host.rstrip('.').split('.')
        valid_dns = (host and len(host) <= 253 and all(
            1 <= len(label) <= 63
            and re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?', label)
            for label in labels))
        if not valid_dns:
            raise ValueError('host must be an IPv4 address or DNS hostname') from address_error
        return host.rstrip('.')


def _validate_port(port):
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('port must be between 1 and 65535')
    return port


def _subject_alt_names(host):
    try:
        name = x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        name = x509.DNSName(host)
    return [name, x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]


def provision(host, port, config_dir, asset_path):
    """Create or update local pairing files without returning or printing secrets."""
    folder = Path(config_dir)
    asset = Path(asset_path)
    config_path = folder / 'config.json'

    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if host is not None:
            config['host'] = validate_host(host)
        elif not config.get('host'):
            raise ValueError('host is required when the existing configuration has no host')
        if port is not None:
            config['port'] = _validate_port(port)
        if not all(config.get(key) for key in ('host', 'port', 'token', 'fingerprint')):
            raise ValueError('existing configuration is incomplete')
        if not (folder / 'key.pem').is_file() or not (folder / 'cert.pem').is_file():
            raise ValueError('existing certificate files are incomplete')
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        if host is None:
            raise ValueError('--host is required for a new configuration')
        selected_host = validate_host(host)
        selected_port = _validate_port(DEFAULT_PORT if port is None else port)
        folder.mkdir(parents=True, exist_ok=True)
        config = {'host': selected_host, 'port': selected_port, 'token': secrets.token_urlsafe(32)}
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
        (folder / 'key.pem').write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        (folder / 'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        config['fingerprint'] = hashlib.sha256(
            cert.public_bytes(serialization.Encoding.DER)).hexdigest()
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')

    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Local pairing prepared. Credentials were written to private files and were not printed.')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Generate private VoiceInput2PC credentials and Android pairing data.')
    parser.add_argument('--host', help='Computer IPv4 address or DNS hostname used by the Android app')
    parser.add_argument('--port', type=int, help='Receiver port (default: 23337 for a new setup)')
    parser.add_argument('--config-dir',
                        default=str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'VoiceInput2PC'),
                        help='Private receiver configuration directory')
    parser.add_argument('--asset',
                        default=str(PROJECT / 'android/app/src/main/assets/pairing.json'),
                        help='Generated Android pairing asset (ignored by Git)')
    args = parser.parse_args(argv)
    try:
        provision(args.host, args.port, args.config_dir, args.asset)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
