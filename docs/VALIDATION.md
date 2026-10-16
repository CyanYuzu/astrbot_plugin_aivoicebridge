# 1.1.0 验收记录

日期：2026-10-16。环境：Windows、AIVoiceBridge 1.1.0、正版 A.I.VOICE2 Editor 2.13.0 / DLL 协议 2。
结构化摘要见 [validation-summary.json](validation-summary.json)。原始本机记录位于被忽略的 `evidence/`。

## 已验证

- `python -m pytest -q`：33 项通过，包括原有一代请求格式、旧命令、二代参数构造、风格校验、停顿排除、旧 HTTP 桥识别和错误展示。
- `tests/e2e_bridge.py`：实际运行 `AIVoiceBridgePlugin.initialize`、`_post_config`、`_get_config`、
  `_get_info` 和命令分发；HTTP 未被模拟。`push`、`status`、`voices`、`health`、`parameters` 均通过。
- 插件向真实 HTTP 桥推送声库 `KizunaAkari_ns_48`、语速 1.25、音高 1.1、抑扬 0.8、音量 0.9、
  原生风格 `{"K":0.2}` 和标准词典。三个一代停顿参数未发送。
- 随后的无参数默认合成请求只传文本及 GSV 兼容字段，经原版 Editor DLL 实际生成 280222 字节 WAV，
  48 kHz / 单声道 / PCM16，时长约 2.919 秒。
- 原生任务日志中的 `rate=1.25`、`emphasis=0.8` 等字段与插件设置一致，状态为 `succeeded`。
  HTTP 收到的 WAV 与原生结果 SHA-256 一致：
  `309ac5610efc64844882c7b4a90c70c3f2b702b0a82ba089b2e50ca14910fda5`。

## 文件与调用对应

| 文件 / 类型 / 方法 | 实际行为 |
|---|---|
| `main.py` / `AIVoiceBridgePlugin._payload` | 一代保持原字段；二代发送后端、声库 ID、词典、风格，排除一代停顿；无效风格在推送前拒绝 |
| `main.py` / `_post_config` | HTTP `POST /config` → AIVoiceBridge 持久默认值 |
| `main.py` / `_get_info`、`aivoice` | 查询 HTTP `/voices`、`/health`、`/parameters`，在事件结果中呈现实际返回 |
| `_conf_schema.json` | WebUI 配置定义，二代 ID、风格、词典及两代差异均有提示 |
| `tests/test_main.py` | 单元测试使用 AstrBot 与 HTTP 替身；不据此宣称完整宿主可用 |
| `tests/e2e_bridge.py` | AstrBot 导入与事件使用替身，插件 HTTP 方法、HTTP 桥、原生合成、WAV 字节为真实执行 |

## 边界

未在远端完整 AstrBot 进程或聊天平台上执行安装、重载和消息发送验收，未变更 VPS 配置。
WebUI 控件渲染、其他 AstrBot 版本、长期压力和听感质量也未验证。
当前结论是插件代码到真实声库的 HTTP 合成链已通过，而不是线上机器人部署已完成。

HTTP 桥自身的 8 声库、4 路并发批量、一代三语言回归及故障恢复结果见
[AIVoiceBridge 验收记录](https://github.com/CyanYuzu/AIVoiceBridge/blob/main/docs/VALIDATION.md)。
