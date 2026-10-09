"""Inspect compressed public artifacts without trusting their raw archive bytes."""

import argparse
import posixpath
import re
import zipfile
from pathlib import Path, PurePosixPath


class VerificationError(RuntimeError):
    pass


PRIVATE_NAMES = {
    'pairing.json', 'config.json', 'cert.pem', 'key.pem', 'messages.db',
    'signing.json',
}
PRIVATE_SUFFIXES = ('.p12', '.pfx', '.jks', '.keystore')
PRIVATE_KEY_MARKERS = (
    b'BEGIN PRIVATE KEY', b'BEGIN RSA PRIVATE KEY', b'BEGIN EC PRIVATE KEY',
)
PAIRING_URI_MARKER = b'voiceinput2pc://pair?p='
TAILCAT_ADDRESS_RX = re.compile(rb'\btc[A-Za-z0-9_-]{40,}\b')
SCANNED_SUFFIXES = ('.txt', '.json', '.pem', '.key', '.conf', '.ini', '.toml',
                    '.yaml', '.yml', '.env', '.dat')


def _safe_name(raw):
    name = raw.replace('\\', '/')
    normalized = posixpath.normpath(name)
    if name.startswith('/') or normalized == '..' or normalized.startswith('../'):
        raise VerificationError(f'unsafe archive path: {raw}')
    return normalized


def _contains_private_key(archive, info):
    carry = b''
    with archive.open(info) as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return False
            sample = carry + chunk
            if any(marker in sample for marker in PRIVATE_KEY_MARKERS):
                return True
            carry = sample[-64:]


def _contains_sensitive_pairing_data(archive, info):
    carry = b''
    with archive.open(info) as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return False
            sample = carry + chunk
            if PAIRING_URI_MARKER in sample or TAILCAT_ADDRESS_RX.search(sample):
                return True
            carry = sample[-4096:]


def verify_archive(path, *, windows=False, apk=False):
    path = Path(path)
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise VerificationError(f'not a readable ZIP archive: {path.name}') from exc
    with archive:
        infos = archive.infolist()
        if not infos:
            raise VerificationError(f'archive is empty: {path.name}')
        names = []
        for info in infos:
            name = _safe_name(info.filename)
            names.append(name)
            base = PurePosixPath(name).name.lower()
            if base in PRIVATE_NAMES or base.endswith(PRIVATE_SUFFIXES):
                raise VerificationError(f'private runtime file in {path.name}: {name}')
            if not info.is_dir() and base.endswith(SCANNED_SUFFIXES):
                if _contains_private_key(archive, info):
                    raise VerificationError(f'private-key marker in {path.name}: {name}')
                if _contains_sensitive_pairing_data(archive, info):
                    raise VerificationError(f'sensitive pairing material in {path.name}: {name}')

        if windows:
            required = ('VoiceInput2PCReceiver.exe', '使用说明.txt')
            for name in required:
                if name not in names:
                    raise VerificationError(f'Windows archive is missing {name}')
            if not any(name.startswith('_internal/') for name in names):
                raise VerificationError('Windows archive is missing _internal runtime files')
            if '_internal/tailcat/tailcat.exe' not in names:
                raise VerificationError('Windows archive is missing embedded Tailcat runtime')
        if apk:
            for name in ('AndroidManifest.xml', 'classes.dex', 'lib/arm64-v8a/libgojni.so'):
                if name not in names:
                    raise VerificationError(f'APK is missing {name}')
            if 'lib/arm64-v8a/libtailcat.so' in names:
                raise VerificationError('APK still contains superseded Tailcat CLI runtime')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--windows', required=True, type=Path)
    args = parser.parse_args()
    verify_archive(args.apk, apk=True)
    verify_archive(args.windows, windows=True)
    print('PASS: compressed release entries contain no private runtime material.')


if __name__ == '__main__':
    main()
