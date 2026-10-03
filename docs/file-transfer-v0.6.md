# VoiceInput2PC v0.6｜手机 → Windows 文件传输

状态：IMPLEMENTED / CI PENDING / REAL DEVICE PENDING
更新：2026-10-03

## 目标

在现有 VoiceInput2PC 连接上增加文件传输，不创建第二套连接体系。

第一阶段：

- Android → Windows
- 单文件
- 最大 200MB
- LAN HTTPS 与 Tailcat 跨网络共用同一协议
- 分块上传
- 断点续传
- SHA-256 完整性校验
- Windows 默认保存到 `Downloads/VoiceInput2PC`

## 架构

```text
Android system file picker
        ↓
ContentResolver
        ↓
SHA-256 + size + MIME
        ↓
/file/begin
        ↓ returns transfer_id + durable offset
/file/chunk
        ↓ repeated binary chunks
/file/complete
        ↓ SHA-256 verify
Windows Downloads/VoiceInput2PC
```

Transport 层不变：

```text
FileTransfer Protocol
        ↓
VoiceInput2PC authenticated HTTPS
        ↓
├─ LAN
└─ Tailcat
```

## 协议

### POST /file/begin

JSON：

```json
{
  "name": "example.pdf",
  "size": 123456,
  "sha256": "<64 hex>",
  "mime": "application/pdf"
}
```

返回：
- `id`
- `offset`
- `size`
- `status`

重新发送同一文件信息时，Windows 根据临时文件返回已持久化 offset。

### POST /file/chunk

Headers：
- Authorization
- X-Transfer-Id
- X-Transfer-Offset

Body：
binary chunk

当前 Android chunk = 512 KiB。
Windows 最大接受单 chunk = 1 MiB。

服务端只有在 offset 与本地 durable file size 完全一致时才追加。

### POST /file/complete

JSON：

```json
{"id":"<transfer id>"}
```

Windows：
1. 检查最终大小
2. 重新计算 SHA-256
3. 与 begin 声明摘要比较
4. 校验成功才从 spool 原子移动到 Downloads

## 安全边界

文件接口沿用 VoiceInput2PC 原有：
- HTTPS
- Bearer token
- certificate fingerprint pinning
- Tailcat encrypted tunnel（跨网络模式）

没有新增公网裸端口。

Android：
- 使用系统 ACTION_OPEN_DOCUMENT
- 只读取用户明确选择的文件
- 不申请广泛存储权限

Windows：
- 拒绝路径穿越
- 拒绝控制字符
- 拒绝 Windows 非法/保留文件名
- 单文件最大 200MB
- 同名目标文件自动使用编号副本
- 完成前只保存在私有 spool 中

## Resume

断线后用户重新选择同一文件：

```text
file/begin
→ Windows returns offset
→ Android skips to offset
→ continue chunks
```

不从头重复发送已经 fsync 的部分。

## Capability Discovery

`/health` 新增：

```json
"features": ["file-upload-v1"]
```

Android 只有确认电脑支持 `file-upload-v1` 后才启用“发送文件到电脑”。

旧 Windows 端不会出现一个必然失败的文件按钮。

## UI

Android 输入页面新增：

> 发送文件到电脑

状态提示：
- 读取 / SHA-256
- 准备发送
- 上传百分比
- 完成文件名
- 失败 + 可重新选择同一文件续传

## 第一阶段不做

- Windows → Android 文件
- 多文件并行
- 文件夹
- Android Share Sheet
- 后台 Foreground Service
- 自动同步
- 大于 200MB
- 云端存储

这些等单文件链路真机稳定后再增加。

## 验收

必须验证：

1. LAN：10MB / 100MB 文件
2. Tailcat 跨网络：10MB / 100MB
3. 上传中断后续传
4. SHA-256 一致
5. 同名文件不覆盖
6. 中文文件名 / emoji 文件名
7. PDF / Office / ZIP / JPG / MP4
8. 超 200MB 明确拒绝
9. 旧 Windows 端按钮禁用
10. App 前后台 / 网络切换行为

只有真实 Android + Windows 验证后才升正式 v0.6。
