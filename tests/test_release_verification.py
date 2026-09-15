import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.verify_release_artifacts import VerificationError, verify_archive


class ReleaseArtifactVerificationTests(unittest.TestCase):
    def write_zip(self, path, entries):
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries.items():
                archive.writestr(name, content)

    def test_deflated_private_key_marker_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'bad.zip'
            self.write_zip(archive, {
                'VoiceInput2PCReceiver.exe': b'exe',
                '_internal/library.dat': b'prefix\n-----BEGIN PRIVATE KEY-----\nsecret',
                '使用说明.txt': '说明'.encode('utf-8'),
            })
            with self.assertRaisesRegex(VerificationError, 'private-key marker'):
                verify_archive(archive, windows=True)

    def test_private_runtime_names_and_keystores_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('config.json', 'nested/messages.db', 'release-signing.p12'):
                archive = Path(folder) / (Path(name).name + '.zip')
                self.write_zip(archive, {name: b'private'})
                with self.subTest(name=name), self.assertRaises(VerificationError):
                    verify_archive(archive)

    def test_clean_windows_and_apk_archives_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            windows = Path(folder) / 'windows.zip'
            apk = Path(folder) / 'app.apk'
            self.write_zip(windows, {
                'VoiceInput2PCReceiver.exe': b'exe',
                '_internal/library.dat': b'public runtime',
                '使用说明.txt': '公开说明'.encode('utf-8'),
            })
            self.write_zip(apk, {
                'AndroidManifest.xml': b'manifest',
                'classes.dex': b'dex',
            })
            verify_archive(windows, windows=True)
            verify_archive(apk, apk=True)


if __name__ == '__main__':
    unittest.main()
