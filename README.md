# VoiceInput2PC｜手机语音输入电脑

用安卓手机输入法，把语音识别文字直接输入 Windows 当前光标位置。

VoiceInput2PC 不传输麦克风声音，也不自己做语音识别。安卓手机负责调用你已经习惯的输入法完成语音转文字；应用只把输入法确认后的文字加密发送给 Windows 接收端，再由接收端写入当前获得焦点的普通输入框。

> 当前为源码预览版。仓库暂不提供通用 APK、EXE 或安装器；请按本文在自己的电脑上生成专用配对信息并构建。不要分享自己生成的 APK、`pairing.json`、令牌、证书或私钥。

## 主要特点

- 使用安卓手机输入法，无需更换输入法，也不使用电脑麦克风。
- 文字直接进入 Windows 当前光标位置，可用于 Word、网页和普通聊天输入框。
- Windows 端使用 Unicode 键盘输入，不占用剪贴板。
- 只输入文字，不会自动按回车，也不会自动发送聊天消息或执行命令。
- 手机端不申请麦克风权限；麦克风权限属于用户选择的手机输入法。
- HTTPS、专用令牌和证书指纹固定共同保护手机到电脑的连接。
- 消息编号去重，连接结果不确定时不会盲目重复输入。

## 运行环境

- Windows 10/11，普通桌面用户会话。
- Android 8 或更高版本。
- 手机与电脑位于同一个可信局域网；不同网络可自行通过私人组网工具建立安全连接。
- 源码构建环境：Python 3.13、JDK 17、Android SDK 35、Gradle 8.10.2。

## 数据流

```text
手机自带/第三方输入法语音识别
            ↓ 已确认文字
VoiceInput2PC 安卓应用
            ↓ HTTPS + 令牌 + 证书固定
VoiceInput2PC Windows 接收端
            ↓ Unicode 键盘输入
Windows 当前光标位置
```

语音识别是否联网、音频发往哪里，取决于你使用的安卓输入法及其隐私政策。VoiceInput2PC 本身只接收输入法已经写入应用文本框的文字。

## 从源码开始

### 1. 准备 Python 环境

在项目根目录打开 PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 生成个人配对文件

先通过 `ipconfig` 找到手机能够访问的电脑 IPv4 地址，再运行：

```powershell
.\.venv\Scripts\python.exe scripts/provision.py --host 192.168.1.20
```

请把示例地址替换成你电脑的实际地址。该命令会在 `%LOCALAPPDATA%\VoiceInput2PC` 生成电脑端配置、证书和私钥，并生成被 Git 忽略的安卓配对文件：

```text
android/app/src/main/assets/pairing.json
```

再次运行时会复用已有凭据；需要修改手机连接地址时，可重新提供 `--host`。

### 3. 启动 Windows 接收端

```powershell
.\.venv\Scripts\python.exe receiver_app.py --show
```

如果需要构建单文件接收端：

```powershell
.\.venv\Scripts\pyinstaller.exe VoiceInput2PCReceiver.spec
```

### 4. 构建安卓应用

确认已安装 JDK 17、Android SDK 35 和 Gradle 8.10.2：

```powershell
Set-Location android
gradle --no-daemon :app:assembleRelease
```

生成文件位于 `android/app/build/outputs/apk/release/app-release.apk`。当前 Release 构建使用本机测试签名，只适合自己安装和验证，不是正式应用商店签名方案。

## 使用方法

1. 让 Windows 上需要输入文字的位置获得焦点。
2. 打开安卓应用，确认顶部显示正确的电脑地址。
3. 点击“开始输入到电脑”。
4. 使用手机输入法的语音按钮说话；输入法确认的新增文字会自动进入电脑。
5. 切换电脑窗口或输入位置前，先在手机端暂停，再重新开始。

## 已知限制

- 不向锁屏桌面、安全桌面、管理员权限高于接收端的程序或终端程序自动输入。
- 手机锁屏、应用进入后台、输入法在确认前中断，都会暂停并保留草稿。
- 当前输入会话绑定开始时选中的电脑窗口；窗口改变后需要重新开始，以免文字进入错误位置。
- 手机输入法修改已经输出的前缀时会暂停，需要人工核对，电脑中已有文字不会被远程删除。
- 接收端把最近文字保存在本机数据库用于异常核对，请把电脑账户视为隐私边界。
- 不建议直接把接收端端口暴露到公网。跨网络使用应优先采用受控的私人组网，并限制可访问设备。

## 测试

电脑端测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

安卓状态机测试与完整安卓构建命令记录在 `docs/superpowers/plans/2026-09-12-voiceinput2pc-publication.md`。

## 项目结构

```text
android/          原生安卓应用
receiver/         Windows 接收、会话和 Unicode 输入
receiver_app.py   Windows 托盘程序入口
scripts/          本地配对、验证和打包辅助脚本
tests/            Python、Java 和真实程序验收测试
docs/             设计与实施说明
```

## 安全与许可证

公开问题请使用 GitHub Issues；安全问题请阅读 [SECURITY.md](SECURITY.md)，不要把配对信息粘贴到公开 Issue。

本项目采用 [MIT License](LICENSE)。
