# VoiceInput2PC v0.5 Tailcat Transport Candidate

状态：IMPLEMENTED / CI + REAL DEVICE GATES

## 产品变化

v0.4.0：

Android
→ LAN HTTPS
→ Windows

v0.5 Candidate：

Android
→ Transport Resolver
├─ LAN HTTPS
└─ Tailcat encrypted tunnel
       ↓
     HTTPS application protocol
       ↓
Windows

用户仍然只使用：
- Windows 接收端
- Android App
- 二维码配对

用户不需要安装 Tailcat，不需要配置 Tailcat，也不需要运行 Tailcat 命令。
Windows 打包时 Tailcat 被收入 VoiceInput2PC 的内部 runtime 目录；
Android 打包时 Tailcat 被收入 APK 的 native runtime。

不需要手工使用 Tailcat CLI。

## 为什么这样集成

Tailcat 不替代 VoiceInput2PC 协议。

VoiceInput2PC 继续负责：
- Token
- Certificate fingerprint pinning
- Session
- Message ID / dedup
- Reverse outbox
- Draft protection
- Windows current-target safety

Tailcat 只负责：
- NAT traversal
- WireGuard encrypted peer path
- DERP relay fallback
- 把远程 23337 映射到 Android localhost

因此 Tailcat 出问题时，LAN HTTPS 可以继续存在。

## 配对兼容

### v1
保持 v0.4.x 原格式：

1
host
port
token
fingerprint

LAN 用户继续使用 v1。

### v2
只用于 Tailcat：

2
tailcat
host
port
token
fingerprint
tailcat-address

Tailcat address 视为敏感连接信息：
- 不记录日志
- 不写 README 示例真实值
- 不进入公开诊断
- 对象 repr/toString 必须 redacted

## Windows

接收端新增可选 Tailcat sidecar。

配对窗口：
- 默认继续显示 LAN QR
- 用户点击“跨网络配对”
- 接收端启动 bundled tailcat.exe
- 获取临时 Tailcat address
- 生成 v2 QR

Windows HTTPS server 本身保持不变。

## Android

APK 内嵌官方 Tailcat arm64 Linux static binary。

运行时：
- App 读取 v2 pairing
- App 启动 Tailcat sidecar
- sidecar forward:
  remote VoiceInput2PC port → 127.0.0.1:ephemeral
- RelayClient 对 localhost 继续发原 HTTPS 请求
- TLS certificate identity 继续按 fingerprint 验证

## Supply-chain

Tailcat binary 不提交 Git。

构建脚本：
1. 固定 Tailcat release 版本
2. 下载官方 checksums.txt
3. 先验证 checksum manifest 的 pinned SHA-256
4. 再验证 Windows / Linux arm64 asset SHA-256
5. 解包进入构建目录
6. Windows ZIP 和 Android APK 都验证 sidecar 存在

## 当前验证

已验证：
- Python v1/v2 pairing
- Java v1/v2 pairing
- v1 pairing backward compatibility
- Tailcat address redaction
- Tailcat asset checksum verification
- Android Debug APK build
- APK contains arm64 Tailcat sidecar

待验证：
- Windows candidate package build
- Windows sidecar actual start
- Android app sandbox 是否允许执行 bundled Tailcat static binary
- Android ↔ Windows real cross-network tunnel
- text send
- reverse receive
- network switching
- reconnect
- battery / latency

## 最重要的 Gate

官方 Tailcat 已明确支持 Android 下的 Termux / adb shell / rooted shell。

但：

> 普通 Android App sandbox 内直接执行被 APK 解包的 Tailcat static binary，仍必须以 OnePlus 15 真机结果为准。

因此在完成真机前：

不得合并 main。
不得发布 v0.5.0。
不得标 VERIFIED。

## Fallback

如果普通 App sandbox 不允许执行 Tailcat binary：

优先路线不是要求用户手工打开 Termux。

下一路线：

Tailcat Go library
→ Android-compatible native bridge / JNI
→ App 内嵌 Transport Provider

保持上层 Pairing / RelayTransport / VoiceInput2PC Protocol 不变。

## 当前开发位置

Branch:
feat/tailcat-transport-v0.5

Draft PR:
#1

main 保持 v0.4.0 稳定版。
