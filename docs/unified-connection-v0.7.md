# VoiceInput2PC v0.7｜统一配对与自动连接

状态：IMPLEMENTED / CI PENDING / REAL DEVICE PENDING
更新：2026-10-03

## 目标

用户不再理解或选择“局域网二维码 / 跨网络二维码”。

目标体验：

```text
第一次
电脑：配对手机
→ 一个二维码
→ 手机扫码一次

以后
打开 VoiceInput2PC
→ 识别同一台电脑
→ 自动选择最佳连接
```

## Unified Pairing v3

v3 把“设备身份”和“当前连接位置”分开。

保存：

- device_id
- device_name
- LAN host
- port
- Tailcat address
- application token
- certificate fingerprint

Wire format：

```text
3
auto
<device_id>
<device_name>
<lan_host>
<port>
<token>
<fingerprint>
<tailcat_address>
```

整体继续使用 URL-safe Base64 放进：

`voiceinput2pc://pair?p=...`

v1 LAN 和 v2 Tailcat 配对仍然可以解码，作为兼容路径。

## Windows 持久设备身份

Receiver config 首次创建后生成稳定：

`device_id`

旧配置升级时自动补：

- device_id
- device_name

“换一组配对码”只轮换：

- token
- HTTPS certificate / fingerprint

不会改变 device_id。

## Windows 持久 Tailcat 身份

旧方案：

`--key=new`

每次启动产生新地址。

v0.7：

```text
%LOCALAPPDATA%/VoiceInput2PC/
└─ tailcat-server.private.json
```

首次生成使用固定 DERP region 的 Tailcat server key。

后续 Windows 重启继续加载同一 key，因此 remote endpoint 保持稳定。

该 key：
- 不进入 Git
- 不进入发布包
- 不打印日志
- 属于本机私密运行数据

## 自动启动

Windows Receiver 启动：

```text
HTTPS Receiver
+
background Tailcat server
```

远程可达不再依赖用户先打开“配对手机”。

如果 Tailcat 暂时启动失败：
- LAN 功能继续可用
- 后续打开配对或下次启动可重试

## Android Connection Manager

v3 pairing 创建一个逻辑 Device Connection。

```text
Device
   ↓
ConnectionManager
   ├─ LAN RelayClient
   └─ Tailcat RelayClient (lazy)
```

策略：

1. LAN connect timeout：约 900ms
2. LAN 成功 → 使用 LAN
3. LAN 失败 → 才启动 Tailcat
4. 当前路径失败 → probe alternate path
5. alternate 健康 → 自动 failover
6. Tailcat 工作时每 30 秒允许快速回探 LAN
7. LAN 恢复 → 自动回切 LAN

Tailcat 是 lazy provider：
LAN 可用时不会无意义启动远程通道。

## 上层透明

以下功能不判断 LAN/Tailcat：

- Text
- Session
- Clipboard return
- File begin/chunk/complete

统一只依赖：

`RelayTransport`

因此文件传输过程中路径故障后，仍可利用 v0.6 的 durable offset 继续恢复。

## 用户界面

Windows 配对页：
- 只显示一个二维码
- 文案：自动连接
- 不再显示“跨网络配对”按钮

Android：
- 保存设备名而不是把 IP 当电脑名称
- 普通界面不展示 Tailcat / DERP / WireGuard

技术路径仅用于高级诊断。

## 安全

统一二维码仍然是敏感凭据，因为包含：
- token
- fingerprint
- Tailcat address

不得：
- 上传 GitHub
- 公开截图
- 粘贴 Issue
- 写普通日志

Tailcat address 即使长期稳定，也仍有 VoiceInput2PC HTTPS token + certificate pinning 二次保护。

## 当前仍未解决

### LAN 地址变化

v3 当前保存配对时的 LAN host。

如果 Windows DHCP 地址变化：
- Tailcat 仍然可连接
- LAN 自动优先可能暂时无法恢复

下一阶段应增加：

`Local Device Discovery / Endpoint Refresh`

候选：
- mDNS / DNS-SD
- authenticated UDP discovery
- local endpoint announcement

目标是：

Device ID 不变，LAN Position 动态更新。

### 多设备 Device Registry

当前 Android 仍以“一台已配对电脑”为主。

v0.7 先解决：

Device Identity + Multi-Endpoint Connection

后续再把 PairingStore 升级为真正：

```text
DeviceRegistry
├─ Office PC
├─ Home PC
└─ Laptop
```

## 验收

正式标 VERIFIED 前必须真机测试：

1. 同 Wi-Fi：自动走 LAN
2. 手机 5G / PC Wi-Fi：自动走 Tailcat
3. Wi-Fi → 5G：自动 failover
4. 5G → 同 Wi-Fi：自动回切 LAN
5. Windows 重启：无需重新扫码，远程仍可连接
6. Text 正常
7. Clipboard return 正常
8. 10MB / 100MB file transfer 正常
9. 文件传输中断后续传
10. v1/v2 旧配对兼容
