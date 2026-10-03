# VoiceInput2PC v0.5.0｜内置跨网络传输

状态：CURRENT / REAL-DEVICE VERIFIED
更新：2026-10-03

## 产品变化

v0.4.0：

```text
Android
→ LAN HTTPS
→ Windows
```

v0.5.0：

```text
Android
→ Transport
├─ LAN HTTPS
└─ Tailcat Go Bridge
      ↓ WireGuard / NAT traversal / DERP fallback
→ HTTPS + token + certificate fingerprint
→ Windows
```

用户只需要 VoiceInput2PC Android + Windows 两端，不需要单独安装 Tailcat/Tailscale。

## Windows

Tailcat v0.7.0 作为内部运行组件随 Windows 包分发。

运行时：
- VoiceInput2PC 启动内部 Tailcat；
- Tailcat 只负责跨网络数据通道；
- VoiceInput2PC 原 HTTPS、Token、证书指纹校验继续保留；
- 最终 Windows ZIP 会在 CI 中解压并实际启动内部 Tailcat，拿到有效地址才算 PASS。

## Android

早期候选方案使用 `ProcessBuilder` 运行 Linux arm64 Tailcat CLI。

真机发现 Android 普通 App 沙箱会导致网络接口枚举失败：

```text
netmon.New ... netlinkrib: permission denied
```

该方案已废弃。

当前方案：

```text
Android Java
→ java.net.NetworkInterface
→ gomobile reverse binding
→ netmon.RegisterInterfaceGetter
→ Tailcat Go Library
→ localhost forward
→ VoiceInput2PC HTTPS
```

Tailcat 被编译为 Android AAR，通过 Go Bridge 在 App 进程内运行，不再启动外部 CLI。

## 真机验证

已验证：
- Windows 内部 Tailcat 能实际启动；
- Android Go Bridge AAR 构建；
- Android Java → Go 网络接口注入；
- OnePlus 15 真机扫码建立跨网络连接；
- Windows ↔ Android 配对闭环；
- v1 LAN pairing 向后兼容；
- v2 cross-network pairing；
- Token / certificate fingerprint 二次验证继续生效。

## 安全

以下内容按敏感连接凭据处理：
- 完整 `voiceinput2pc://pair?p=...`；
- Token；
- 完整证书指纹；
- 完整 Tailcat `tc...` 地址；
- Windows 本机配置、私钥和消息数据库。

要求：
- 不提交 Git；
- 不写公开日志；
- 不写 README 真实示例；
- 错误诊断对 Tailcat 地址使用 `tc<redacted>`；
- 发布包自动扫描并拒绝敏感配对材料。

## 已知限制

当前跨网络 Tailcat 地址采用临时身份。Windows 接收端重启后，跨网络连接可能需要重新打开“跨网络配对”并扫码。

这是 v0.5.0 已知产品限制，后续可将 Tailcat 身份迁移到 VoiceInput2PC 私有配置目录，实现稳定地址和自动重连。
