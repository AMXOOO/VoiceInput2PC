import ast
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/provision.py'


def load_provision_module():
    source = SCRIPT.read_text(encoding='utf-8')
    functions = {node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
    if not {'validate_host', 'provision', 'main'} <= functions:
        raise AssertionError('provision.py must expose validate_host(), provision(), and main()')
    spec = importlib.util.spec_from_file_location('voiceinput2pc_provision', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProvisionTests(unittest.TestCase):
    def test_import_has_no_filesystem_side_effects(self):
        load_provision_module()
        with tempfile.TemporaryDirectory() as folder:
            environment = os.environ.copy()
            environment['LOCALAPPDATA'] = folder
            result = subprocess.run(
                [sys.executable, '-c', 'import scripts.provision'],
                cwd=ROOT, env=environment, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([], list(Path(folder).iterdir()))

    def test_new_configuration_requires_explicit_host(self):
        module = load_provision_module()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            with self.assertRaisesRegex(ValueError, 'host'):
                module.provision(None, 23337, base / 'config', base / 'pairing.json')

    def test_host_validation_accepts_ipv4_and_dns(self):
        module = load_provision_module()
        self.assertEqual('192.0.2.10', module.validate_host('192.0.2.10'))
        self.assertEqual('desktop.example.test', module.validate_host('desktop.example.test'))
        for invalid in ('', 'https://desktop', 'desktop:23337', 'bad host', '-desktop.test'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    module.validate_host(invalid)

    def test_generates_private_files_only_at_selected_paths_without_printing_secrets(self):
        module = load_provision_module()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            config_dir = base / 'private-config'
            asset = base / 'generated' / 'pairing.json'
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                module.provision('192.0.2.10', 24444, config_dir, asset)

            config = json.loads((config_dir / 'config.json').read_text(encoding='utf-8'))
            pairing = json.loads(asset.read_text(encoding='utf-8'))
            self.assertEqual(config, pairing)
            self.assertEqual('192.0.2.10', config['host'])
            self.assertEqual(24444, config['port'])
            self.assertTrue((config_dir / 'key.pem').is_file())
            self.assertTrue((config_dir / 'cert.pem').is_file())
            self.assertNotIn(config['token'], output.getvalue())
            self.assertNotIn(config['fingerprint'], output.getvalue())

    def test_cli_without_asset_only_creates_receiver_configuration(self):
        module = load_provision_module()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            public_asset = ROOT / 'android/app/src/main/assets/pairing.json'
            self.assertFalse(public_asset.exists())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                module.main(['--host', '192.0.2.10', '--config-dir', str(base / 'config')])

            self.assertTrue((base / 'config' / 'config.json').is_file())
            self.assertEqual([], list(base.glob('pairing.json')))
            self.assertFalse(public_asset.exists())
            self.assertIn('credentials were not printed', output.getvalue().lower())


if __name__ == '__main__':
    unittest.main()
