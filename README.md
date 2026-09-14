# VoiceInput2PC｜手机语音输入电脑

用安卓手机输入法完成语音识别，把确认后的文字直接输入 Windows 当前光标位置。可用于 Word、网页、Codex 和普通聊天输入框。

VoiceInput2PC 不传输麦克风声音，也不自己做语音识别。它只负责把手机输入法已经转换好的文字，通过加密连接送到自己的电脑。

## 下载成品

打开 [GitHub 最新版本下载页](https://github.com/AMXOOO/VoiceInput2PC/releases/latest)，下载这两个文件：

- `VoiceInput2PC-Windows-v0.3.1.zip`：Windows 电脑接收端；
- `VoiceInput2PC-Android-v0.3.0.apk`：安卓手机端。

第一次使用只需四步：

1. Windows 端是免安装便携版，不是安装程序。请完整解压压缩包，保留 `_internal` 文件夹，再双击 `VoiceInput2PCReceiver.exe`；不要把 EXE 单独复制出来运行。首次启动选择电脑地址，通常保持默认即可。
2. Windows 弹出防火墙提示时，只允许“专用网络”，不要允许公共网络。接收端会显示配对二维码。
3. 安卓手机安装 APK，用系统相机扫描二维码并选择用 VoiceInput2PC 打开；也可复制完整配对码，在手机应用中粘贴后导入。
4. 在电脑上点中要输入的位置，手机上点“开始输入到电脑”，再使用安卓手机输入法的语音按钮。

Windows 程序目前没有商业代码签名，SmartScreen 可能显示提醒。请确认文件来自本仓库 Release，并可用同页的 `SHA256SUMS.txt` 核对后，再选择“更多信息 → 仍要运行”；不要全局关闭 SmartScreen。安卓若提示“安装未知应用”，只为本次下载所用的浏览器或文件管理器临时允许，安装完成后可以关闭该权限。

二维码和完整配对码相当于密码，请勿截图公开或发给不信任的人。

## 它怎样工作

```text
手机输入法语音识别
        ↓ 已确认文字
VoiceInput2PC 安卓应用
        ↓ HTTPS + 令牌 + 证书指纹固定
VoiceInput2PC Windows 接收端
        ↓ Unicode 键盘输入
Windows 当前光标位置
```

语音识别是否联网、音频发往哪里，取决于你使用的安卓输入法及其隐私政策。VoiceInput2PC 本身不使用电脑麦克风，安卓应用也不申请麦克风或相机权限；扫码由系统相机完成。

## 主要特点

- 文字直接进入 Windows 当前光标位置，不需要复制粘贴。
- Windows 端使用 Unicode 键盘输入，不占用剪贴板。
- 只输入文字，不会自动按回车，也不会自动发送聊天消息或执行命令。
- 每次开始都绑定当时选中的电脑窗口；窗口改变后自动停止，避免输错位置。
- HTTPS、专用令牌和证书指纹固定共同保护手机到电脑的连接。
- 消息编号去重，结果不确定时保留草稿，不盲目重复输入。

## 运行环境和网络

- Windows 10/11 普通桌面用户会话；
- Android 8 或更高版本；
- 手机和电脑能够互相访问。家庭里通常连接同一个 Wi-Fi 即可。

公司网络即使显示在同一网段，也可能开启客户端隔离或终端防火墙。此时可先确认 Windows 防火墙仅在专用网络放行接收端；若公司策略仍阻断设备互访，应遵守公司规定，不要自行绕过。跨网络使用可选择 Tailscale 等受控私人组网，不要把 23337 端口直接暴露到公网。

## 日常使用

1. 先在 Windows 上点中需要输入文字的位置。
2. 手机上点击“开始输入到电脑”。
3. 使用手机输入法的语音按钮说话；输入法确认后的新增文字会自动进入电脑。
4. 需要切换电脑窗口或输入位置时，先暂停，再在新位置重新开始。
5. 需要连接另一台电脑时，点击手机顶部的电脑地址，重新扫码配对。

## 已知限制

- 不向锁屏桌面、安全桌面、管理员权限高于接收端的程序或终端程序自动输入。
- 手机锁屏、应用进入后台、输入法在确认前中断，都会暂停并保留草稿。
- 手机输入法修改已经输出的前缀时会暂停；电脑中已有文字不会被远程删除，需要人工核对后重置。
- Windows 接收端把最近文字保存在本机数据库，用于异常核对；请把电脑账户视为隐私边界。

## 从源码开始

下载成品不需要以下步骤。开发者可在项目根目录准备环境：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

运行 Windows 接收端：

```powershell
.\.venv\Scripts\python.exe receiver_app.py
```

手动启动默认显示状态窗口；只有开机启动等无人值守场景才使用
`--background` 收起到系统托盘。程序已运行时再次手动启动，会把已有窗口调到前台。

首次启动会在 `%LOCALAPPDATA%\VoiceInput2PC` 生成本机令牌、证书和私钥，并显示二维码。也可用 `scripts/provision.py --host 192.168.1.20` 进行无界面配置；示例地址必须替换为实际地址，默认不会生成安卓资产文件。

构建通用安卓调试包：

```powershell
gradle -p android --no-daemon :app:assembleDebug
```

正式 Release 构建要求通过环境变量提供独立签名：`VOICEINPUT2PC_KEYSTORE`、`VOICEINPUT2PC_STORE_PASSWORD`、`VOICEINPUT2PC_KEY_ALIAS`、`VOICEINPUT2PC_KEY_PASSWORD`。不得把签名文件或密码提交到仓库。

运行电脑端测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 项目结构

```text
android/          原生安卓应用
receiver/         Windows 接收、会话和 Unicode 输入
receiver_app.py   Windows 托盘程序入口
scripts/          本地配置、验证和发布构建脚本
tests/            Python、Java 和真实程序验收测试
docs/             设计与实施说明
```

## 安全与许可证

公开问题请使用 GitHub Issues；安全问题请阅读 [SECURITY.md](SECURITY.md)，不要把配对信息粘贴到公开 Issue。

本项目采用 [MIT License](LICENSE)。
