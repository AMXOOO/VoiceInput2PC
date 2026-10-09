import os
import subprocess
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
        self.assertIn('versionCode 5', build)
        self.assertIn("versionName '0.5.0'", build)
        self.assertIn("rootProject.name = 'VoiceInput2PC'", settings)
        self.assertIn('android:label="手机万能输入法"', manifest)
        self.assertIn("'app': 'VoiceInput2PC'", server)
        self.assertIn("/ 'VoiceInput2PC'", desktop)
        self.assertIn("APP_VERSION = '0.5.0'", desktop)
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

    def test_windows_receiver_has_version_metadata_and_disables_upx(self):
        spec = (ROOT / 'VoiceInput2PCReceiver.spec').read_text(encoding='utf-8')
        version = (ROOT / 'windows_version_info.txt').read_text(encoding='utf-8')
        self.assertIn("version='windows_version_info.txt'", spec)
        self.assertIn('exclude_binaries=True', spec)
        self.assertIn('coll = COLLECT(', spec)
        self.assertIn('upx=False', spec)
        self.assertIn("StringStruct('ProductVersion', '0.5.0')", version)
        self.assertIn("StringStruct('CompanyName', 'AMXOOO')", version)

    def test_public_documentation_explains_scope_and_safety(self):
        required = ('README.md', 'LICENSE', 'SECURITY.md', '.gitignore')
        for name in required:
            self.assertTrue((ROOT / name).is_file(), name)

        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        for phrase in (
                'VoiceInput2PC', '手机万能输入法', '安卓手机输入法',
                'Windows 当前光标', '下载成品', '不使用电脑麦克风',
                '不占用剪贴板', '不会自动按回车', 'Android 8',
                'Windows 10/11', 'v0.5.0', '跨网络',
                'https://github.com/AMXOOO/VoiceInput2PC/releases/latest',
                '系统相机', 'SmartScreen', '安装未知应用', '专用网络',
                '免安装便携版', '保留 `_internal` 文件夹',
                '不要把 EXE 单独复制出来运行', '发送剪贴板到手机',
                '手机上点“接收”'):
            self.assertIn(phrase, readme)
        self.assertLess(readme.index('## 下载成品'), readme.index('## 从源码开始'))
        self.assertNotIn('源码预览版', readme)
        self.assertNotIn('暂不提供通用', readme)

        license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        self.assertIn('MIT License', license_text)
        self.assertIn('Copyright (c) 2026 AMXOOO', license_text)

        security = (ROOT / 'SECURITY.md').read_text(encoding='utf-8')
        self.assertIn('pairing.json', security)
        self.assertIn('私钥', security)
        self.assertIn('令牌', security)
        self.assertIn('二维码', security)
        self.assertIn('相当于密码', security)
        self.assertIn('换一组配对码', security)
        self.assertIn('明确点击“发送剪贴板到手机”', security)

    def test_generated_and_private_files_are_ignored(self):
        ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
        for entry in (
                'android/app/src/main/assets/pairing.json', '*.pem', '*.db',
                '*.apk', '*.exe', '*.log', '*.jks', '*.keystore'):
            self.assertIn(entry, ignore)

    def test_public_source_has_no_personal_network_defaults(self):
        live_test = (ROOT / 'android/app/src/androidTest/java/io/github/amxooo/voiceinput2pc/LiveRelayTest.java').read_text(encoding='utf-8')
        self.assertNotIn('arguments.getString("pairing",', live_test)
        self.assertIn('arguments.getString("pairing")', live_test)


class ReleaseBuildTests(unittest.TestCase):
    def test_public_app_has_no_bundled_private_pairing(self):
        self.assertFalse((ROOT / 'android/app/src/main/assets/pairing.json').exists())
        source = (ROOT / 'android/app/src/main/java/io/github/amxooo/voiceinput2pc/MainActivity.java').read_text(encoding='utf-8')
        self.assertNotIn('getAssets().open("pairing.json")', source)

    def test_release_output_and_names_are_explicit(self):
        ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
        script = (ROOT / 'scripts/build_public_release.ps1').read_text(encoding='utf-8')
        self.assertIn('release/output/', ignore)
        for name in ('VoiceInput2PC-Android-v0.5.0.apk',
                     'VoiceInput2PC-Windows-v0.5.0.zip', 'SHA256SUMS.txt'):
            self.assertIn(name, script)
        self.assertIn("dist\\VoiceInput2PCReceiver", script)
        self.assertIn('connectedDebugAndroidTest', script)
        self.assertIn('verify_release_artifacts.py', script)
        self.assertIn('Expand-Archive -LiteralPath $publicZip', script)
        self.assertIn('$packagedExe', script)
        self.assertIn("scripts\\verify_first_run_ui.py", script)
        self.assertIn("scripts\\verify_receiver_runtime.py", script)

    def test_release_signing_comes_only_from_required_environment(self):
        build = (ROOT / 'android/app/build.gradle').read_text(encoding='utf-8')
        for name in ('VOICEINPUT2PC_KEYSTORE', 'VOICEINPUT2PC_STORE_PASSWORD',
                     'VOICEINPUT2PC_KEY_ALIAS', 'VOICEINPUT2PC_KEY_PASSWORD'):
            self.assertIn(name, build)

    def test_build_script_refuses_missing_signing_environment(self):
        script = ROOT / 'scripts/build_public_release.ps1'
        environment = os.environ.copy()
        for name in ('VOICEINPUT2PC_KEYSTORE', 'VOICEINPUT2PC_STORE_PASSWORD',
                     'VOICEINPUT2PC_KEY_ALIAS', 'VOICEINPUT2PC_KEY_PASSWORD'):
            environment.pop(name, None)
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-File', str(script), '-ValidateOnly'],
            cwd=ROOT, env=environment, text=True, capture_output=True, timeout=20)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('VOICEINPUT2PC_KEYSTORE', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
