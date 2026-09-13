"""Create private receiver credentials; optionally export a local Android asset."""

import argparse
import json
import os
from pathlib import Path

from receiver.pairing import (
    DEFAULT_PORT,
    load_pairing,
    prepare_receiver,
    validate_host as _validate_host,
)


def validate_host(raw):
    return _validate_host(raw)


def provision(host, port, config_dir, asset_path=None):
    """Create or update pairing files without returning or printing secrets."""
    folder = Path(config_dir)
    if (folder / 'config.json').exists():
        current = load_pairing(folder)
        selected_host = current.host if host is None else validate_host(host)
        selected_port = current.port if port is None else port
    else:
        if host is None:
            raise ValueError('--host is required for a new configuration')
        selected_host = validate_host(host)
        selected_port = DEFAULT_PORT if port is None else port

    pairing = prepare_receiver(folder, selected_host, selected_port)
    if asset_path is not None:
        asset = Path(asset_path)
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text(json.dumps({
            'host': pairing.host,
            'port': pairing.port,
            'token': pairing.token,
            'fingerprint': pairing.fingerprint,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Local pairing prepared; credentials were not printed.')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Generate private VoiceInput2PC credentials.')
    parser.add_argument('--host', help='Computer IPv4 address or DNS hostname')
    parser.add_argument('--port', type=int, help='Receiver port (default: 23337)')
    parser.add_argument(
        '--config-dir',
        default=str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'VoiceInput2PC'),
        help='Private receiver configuration directory')
    parser.add_argument(
        '--asset',
        help='Optional local Android pairing asset; never publish this file')
    args = parser.parse_args(argv)
    try:
        provision(args.host, args.port, args.config_dir, args.asset)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
