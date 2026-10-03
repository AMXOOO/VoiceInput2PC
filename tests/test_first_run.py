import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from receiver.pairing import detect_private_addresses, load_pairing, prepare_receiver
from receiver.first_run import autostart_command, choose_default_address, pairing_view_model


class FirstRunTests(unittest.TestCase):
    def test_ui_decisions_are_deterministic_and_keep_pairing_in_memory(self):
        self.assertEqual(
            '192.168.1.20',
            choose_default_address(['100.64.0.2', '10.0.0.8', '192.168.1.20']))
        self.assertEqual(
            r'"C:\Program Files\VoiceInput2PCReceiver.exe" --background',
            autostart_command(Path(r'C:\Program Files\VoiceInput2PCReceiver.exe')))

        with tempfile.TemporaryDirectory() as folder:
            pairing = prepare_receiver(Path(folder) / 'receiver', '192.168.1.20', 23337)
            view = pairing_view_model(pairing)
            self.assertEqual('192.168.1.20:23337', view.endpoint)
            self.assertTrue(view.uri.startswith('voiceinput2pc://pair?p='))
            self.assertNotIn(pairing.token, repr(view))
            self.assertNotIn(pairing.fingerprint, repr(view))

    def test_prepare_receiver_creates_and_reuses_private_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                first = prepare_receiver(target, '192.168.1.20', 23337)
                second = prepare_receiver(target, '192.168.1.21', 24444)

            self.assertEqual(first.token, second.token)
            self.assertEqual(first.fingerprint, second.fingerprint)
            self.assertEqual(first.device_id, second.device_id)
            self.assertEqual(first.device_name, second.device_name)
            self.assertRegex(first.device_id, r'^[0-9a-f]{32}
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_regeneration_rotates_credentials_but_keeps_device_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            first = prepare_receiver(target, '192.168.1.20', 23337)
            second = prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertNotEqual(first.token, second.token)
            self.assertNotEqual(first.fingerprint, second.fingerprint)
            self.assertEqual(first.device_id, second.device_id)
            self.assertEqual(first.device_name, second.device_name)

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
)
            self.assertTrue(first.device_name)
            self.assertEqual('192.168.1.21', second.host)
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
)
            self.assertEqual('192.168.1.21', second.host)
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_regeneration_rotates_credentials_but_keeps_device_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            first = prepare_receiver(target, '192.168.1.20', 23337)
            second = prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertNotEqual(first.token, second.token)
            self.assertNotEqual(first.fingerprint, second.fingerprint)
            self.assertEqual(first.device_id, second.device_id)
            self.assertEqual(first.device_name, second.device_name)

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
)
            self.assertTrue(first.device_name)
            self.assertEqual('192.168.1.21', second.host)
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
)
            self.assertTrue(first.device_name)
            self.assertEqual('192.168.1.21', second.host)
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_regeneration_rotates_credentials_but_keeps_device_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            first = prepare_receiver(target, '192.168.1.20', 23337)
            second = prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertNotEqual(first.token, second.token)
            self.assertNotEqual(first.fingerprint, second.fingerprint)
            self.assertEqual(first.device_id, second.device_id)
            self.assertEqual(first.device_name, second.device_name)

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
)
            self.assertTrue(first.device_name)
            self.assertEqual('192.168.1.21', second.host)
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
)
            self.assertEqual('192.168.1.21', second.host)
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_regeneration_rotates_credentials_but_keeps_device_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            first = prepare_receiver(target, '192.168.1.20', 23337)
            second = prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertNotEqual(first.token, second.token)
            self.assertNotEqual(first.fingerprint, second.fingerprint)
            self.assertEqual(first.device_id, second.device_id)
            self.assertEqual(first.device_name, second.device_name)

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
)
            self.assertTrue(first.device_name)
            self.assertEqual('192.168.1.21', second.host)
            self.assertEqual(24444, second.port)
            self.assertEqual(second, load_pairing(target))
            for name in ('config.json', 'cert.pem', 'key.pem'):
                self.assertTrue((target / name).is_file(), name)
            self.assertNotIn(first.token, output.getvalue())
            self.assertNotIn(first.fingerprint, output.getvalue())

    def test_failed_regeneration_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receiver'
            original = prepare_receiver(target, '192.168.1.20', 23337)
            snapshots = {name: (target / name).read_bytes()
                         for name in ('config.json', 'cert.pem', 'key.pem')}

            with mock.patch('receiver.pairing.rsa.generate_private_key',
                            side_effect=RuntimeError('generation failed')):
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    prepare_receiver(target, '192.168.1.20', 23337, regenerate=True)

            self.assertEqual(original, load_pairing(target))
            self.assertEqual(snapshots, {name: (target / name).read_bytes()
                                         for name in snapshots})

    def test_detect_private_addresses_filters_and_deduplicates(self):
        candidates = ('127.0.0.1', '169.254.1.2', '8.8.8.8', '100.69.95.78',
                      '192.168.1.20', '192.168.1.20', '10.0.0.8', 'bad')

        self.assertEqual(
            ['192.168.1.20', '10.0.0.8', '100.69.95.78'],
            detect_private_addresses(candidates))

    def test_load_pairing_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            (target / 'config.json').write_text(json.dumps({'host': 'pc.lan'}), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_pairing(target)


if __name__ == '__main__':
    unittest.main()
