# VoiceInput2PC v0.6｜统一设备连接

状态：IMPLEMENTED / CI RUNNING / REAL DEVICE PENDING
更新：2026-10-03

## 目标

用户只配对一次，不再区分“局域网二维码”和“跨网络二维码”。

配对对象是：

> 这台电脑

而不是某个 IP 或某个 Tailcat 地址。

## Pairing v3

v1：
LAN only

v2：
Tailcat only

v3：
Unified Device

```text
device_id
lan_host
port
token
fingerprint
tailcat_address
```

v1 / v2 继续兼容。

## Device Identity

Windows 首次建立配置时生成稳定 `device_id`。

它不会因为：
- DHCP 改 IP
- Wi-Fi 变化
- 配对凭据轮换

而变化。

“换一组配对码”只轮换：
- token
- certificate
- fingerprint

不改变 device_id。

## Windows

Windows 启动后：

1. 启动 HTTPS Receiver
2. 后台启动内部 Tailcat Server
3. Tailcat 使用 VoiceInput2PC 自己的稳定私有 key
4. 远程 endpoint 在 Windows 重启后保持稳定

因此已配对手机不需要用户再次打开“配对手机”来激活跨网络通道。

## 一个二维码

打开“配对手机”：

```text
Windows current LAN endpoint
+ stable Tailcat endpoint
+ device_id
+ token
+ fingerprint
→ Pairing v3 QR
```

界面只显示：

> 扫码一次，之后自动连接

不再提供“局域网配对 / 跨网络配对”两个用户概念。

## Android ConnectionManager

```text
Business Layer
Text / Clipboard / File
        ↓
ConnectionManager
        ├─ LAN HTTPS
        └─ Tailcat + HTTPS
```

### 默认

LAN 优先。

LAN：
- connect timeout 1.2s
- read timeout 3.5s

Tailcat：
- connect timeout 10s
- read timeout 20s

## Failover

LAN 请求失败：

```text
LAN
↓ failure
Tailcat health
↓
Tailcat
↓
retry same logical operation
```

Tailcat 请求失败时也会尝试 LAN。

要求业务请求可幂等 / 可恢复：

- Text：message id 去重
- Clipboard receive/ack：idempotent
- File begin/chunk：offset protocol
- File complete：completion receipt

## 自动切回 LAN

当前走 Tailcat 时：

每 20 秒最多做一次轻量 LAN health probe。

发现 LAN 恢复：

```text
Tailcat active
↓
LAN health success
↓
active route = LAN
```

用户不操作。

## DHCP / LAN IP 变化

Windows `/health` 在认证后返回：

```json
"lan_hosts": [
  "192.168.x.x",
  "10.x.x.x"
]
```

手机通过 Tailcat 仍可获取电脑当前 LAN endpoint。

因此：

```text
old LAN IP fails
↓
Tailcat reaches same device
↓
learn current LAN IP
↓
next LAN probe succeeds
↓
return to LAN
```

不需要另加 UDP 广播服务。

## 安全

`lan_hosts` 只在通过 Bearer token 的 HTTPS health 请求后返回。

以下仍是敏感凭据：
- token
- certificate fingerprint
- Tailcat address
- full pairing URI
- private key

device_id 是设备标识，不是认证凭据。

## 用户界面

v3 手机端显示：

> 这台电脑 · 自动连接 · 更换 ›

而不是固定 IP。

技术链路只在诊断信息中出现。

## 后续

- 多电脑 Device Registry
- 设备显示名称
- route telemetry（仅本机）
- Happy Eyeballs 并发竞速
- network-change event 主动切换
- Wi-Fi ↔ 5G 文件续传真机验证
