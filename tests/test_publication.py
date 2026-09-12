import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicIdentityTests(unittest.TestCase):
    def test_public_identity_is_consistent(self):
        build = (ROOT / 'android/app/build.gradle').read_text(encoding='utf-8')
        settings = (ROOT / 'android/settings.gradle').read_text(encoding='utf-8')
        manifest = (ROOT / 'android/app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
        server = (ROOT / 'receiver/http_server.py').read_text(encoding='utf-8')
        desktop = (ROOT / 'receiver_app.py').read_text(encoding='utf-8')

        self.assertIn("applicationId 'io.github.amxooo.voiceinput2pc'", build)
        self.assertIn("rootProject.name = 'VoiceInput2PC'", settings)
        self.assertIn('android:label="语音输入电脑"', manifest)
        self.assertIn("'app': 'VoiceInput2PC'", server)
        self.assertIn("/ 'VoiceInput2PC'", desktop)
        self.assertNotIn('随手输入', desktop)

    def test_java_packages_use_public_namespace(self):
        java_files = list((ROOT / 'android/app/src').rglob('*.java')) + list((ROOT / 'tests').glob('*.java'))
        self.assertGreater(len(java_files), 0)
        for path in java_files:
            source = path.read_text(encoding='utf-8')
            self.assertNotIn('package local.pockettype;', source, str(path))
            self.assertNotIn('Class.forName("local.pockettype.', source, str(path))

    def test_public_receiver_build_name(self):
        self.assertTrue((ROOT / 'VoiceInput2PCReceiver.spec').is_file())
        self.assertFalse((ROOT / 'PocketTypeReceiver.spec').exists())

    def test_public_documentation_explains_scope_and_safety(self):
        required = ('README.md', 'LICENSE', 'SECURITY.md', '.gitignore')
        for name in required:
            self.assertTrue((ROOT / name).is_file(), name)

        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        for phrase in (
                'VoiceInput2PC', '手机语音输入电脑', '安卓手机输入法',
                'Windows 当前光标', '源码预览版', '不使用电脑麦克风',
                '不占用剪贴板', '不会自动按回车', 'Android 8',
                'Windows 10/11', 'scripts/provision.py --host'):
            self.assertIn(phrase, readme)

        license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        self.assertIn('MIT License', license_text)
        self.assertIn('Copyright (c) 2026 AMXOOO', license_text)

        security = (ROOT / 'SECURITY.md').read_text(encoding='utf-8')
        self.assertIn('pairing.json', security)
        self.assertIn('私钥', security)
        self.assertIn('令牌', security)

    def test_generated_and_private_files_are_ignored(self):
        ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
        for entry in (
                'android/app/src/main/assets/pairing.json', '*.pem', '*.db',
                '*.apk', '*.exe', '*.log', '*.jks', '*.keystore'):
            self.assertIn(entry, ignore)

    def test_public_source_has_no_personal_network_defaults(self):
        live_test = (ROOT / 'android/app/src/androidTest/java/io/github/amxooo/voiceinput2pc/LiveRelayTest.java').read_text(encoding='utf-8')
        self.assertNotIn('arguments.getString("host",', live_test)
        self.assertIn('arguments.getString("host")', live_test)


if __name__ == '__main__':
    unittest.main()
