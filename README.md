# AIVoiceBridge 参数控制插件

在 AstrBot 中设置 **A.I.VOICE 一代或二代** 的默认声库和语音参数。
1.1.0 增加二代声库 ID、原生风格及词典设置，保留一代参数和已有命令。
音频仍由 AstrBot 内置的 `gsv_tts_selfhost` provider 从 `/tts` 获取；本插件把默认参数写入 HTTP 桥的 `/config`。

## 依赖与安装

1. Windows 本机运行 [AIVoiceBridge](https://github.com/CyanYuzu/AIVoiceBridge) **1.1.0**。
2. 使用二代时，先在正版 Editor 中安装 [AIVoice2-Bridge](https://github.com/CyanYuzu/AIVoice2-Bridge) 协议 2 DLL，正常打开 Editor。
3. 在 AstrBot WebUI 安装或更新本插件，自动安装 `requirements.txt` 中的 `httpx`；重载插件。
4. AstrBot 的 GSV 自托管 provider 与本插件配置相同的 HTTP 地址。
   远端部署继续使用现有 SSH 反向隧道；同机部署直接访问 HTTP 桥。

二代本地启动示例（在 AIVoiceBridge 仓库根目录）：

```powershell
.\AIVoiceBridgeCSharp\bin\Release\net472\AIVoiceBridgeCSharp.exe --engine aivoice2 --port 18765
```

HTTP 桥是原有组件；本插件不启动 Editor 或任何本地辅助进程，也不会修改 Editor DLL。
如需同时使用一代与二代，请运行两个不同端口的 HTTP 桥，并为 AstrBot 配置对应地址。
后端由 HTTP 桥启动参数固定，插件的 `engine` 仅用于匹配校验，不能远程切换运行中的后端。

## 从一代配置迁移到二代

1. 将本地 HTTP 桥更新到 1.1.0，以 `--engine aivoice2` 启动。
2. 将本插件 `engine` 设为 `aivoice2`，`api_base` 指向该 HTTP 实例。
3. 执行 `/aivoice voices`，把返回的声库 **id** 填入 `voice`，例如 `YuzukiYukari_ns_48`。
   也可把 `voice` 留空，使用二代首个可用声库。原来的一代日文预设名需要手动清空或替换。
4. 先使用 `styles={}`、`language=standard`，重载插件或执行 `/aivoice push`，再用 `/aivoice status` 确认。
5. AstrBot 的 TTS provider 继续使用 `gsv_tts_selfhost`，请求只含文本时也会使用推送后的默认参数。
   清空 GPT/SoVITS 模型路径，将 provider `timeout` 设为 360 秒（大于默认桥接超时及取消确认时间）。

一代用户保持 `engine=aivoice`、现有预设名和参数即可；旧配置缺少 `engine` 时仍按一代处理。
一代和二代 HTTP 桥使用独立的默认配置文件，不互相覆盖。

## WebUI 配置

| 配置项 | 说明 | 默认 |
|---|---|---|
| `engine` | `aivoice` 一代 / `aivoice2` 二代，必须与 HTTP 桥一致 | `aivoice` |
| `api_base` | 从 AstrBot 能访问的 HTTP 桥地址 | `http://127.0.0.1:18765` |
| `voice` | 一代预设名 / 二代声库 ID；二代留空会清除旧默认 | 空 |
| `volume` | 一代 0–5；二代 0–2 | 1.0 |
| `speed` | 0.5–4；二代映射 `rate` | 1.0 |
| `pitch` | 0.5–2 | 1.0 |
| `pitch_range` | 0–2，二代映射 `emphasis` | 1.0 |
| `middle_pause` | 仅一代日语，80–500 整数毫秒 | 150 |
| `long_pause` | 仅一代日语，80–2000 整数毫秒 | 370 |
| `sentence_pause` | 仅一代日语，0–10000 整数毫秒 | 800 |
| `language` | 仅二代，`standard` / `kansai` 日语词典 | `standard` |
| `styles` | 仅二代，原生标签到权重的 JSON 字符串 | `{}` |
| `http_timeout` | 配置与查询超时，秒；不是 provider 合成超时 | 20 |
| `auto_push` | 插件加载后推送一次默认配置 | true |

例如 `styles` 填 `{"J":0.3,"A":0.2}`，但必须先确认该声库在 `/aivoice voices` 中返回这些标签。
权重为 0–1，总和不超过 1；`{}` 明确清除风格，不推测未知标签含义。
`standard`、`kansai` 是日语词典选项，不是中文/英文模型转换。

二代推送会排除界面中的三个一代停顿参数，因为当前 DLL 未暴露对应能力；
直接向 HTTP API 传入这些参数会明确报错。本插件不把它们伪装成可用的二代设置。
切换声库后若风格标签不再支持，请修改或清空 `styles`。

## 命令

- `/aivoice`、`/aivoice status`：查看桥接持久默认参数及后端。
- `/aivoice push`：推送插件配置。
- `/aivoice voices`：查询实际安装的声库及二代原生风格。
- `/aivoice health`：检查实际 Editor 连接、就绪状态和二代队列。
- `/aivoice parameters`：查询原厂参数范围及不支持的字段。

修改配置后请重载插件或执行 `push`。后端选错时返回 `ENGINE_MISMATCH`；Editor 未打开时返回
`EDITOR_UNAVAILABLE`。命令会展示 HTTP 桥的错误代码和说明。HTTP 桥提供额外的任务查询及恢复接口，
详见其 README；二代超时后无法确认取消时，应先检查任务而非直接反复重试。

## 验证

```shell
python -m pip install -r requirements-dev.txt
python -m pytest -q
# 独立测试配置的真实 HTTP 桥和正版 Editor 均已运行时：
python tests/e2e_bridge.py --api-base http://127.0.0.1:19765
```

单元测试隔离 AstrBot 注册与事件对象。真实合成验收运行本插件的实际 HTTP 方法、命令及初始化逻辑，
HTTP 调用和声库合成都是真实执行；未据此宣称 VPS 上的完整 AstrBot 进程或聊天平台消息发送已验收。
验收范围见 [docs/VALIDATION.md](docs/VALIDATION.md)。本机原始记录在被忽略的 `evidence/` 中。

## License

[MIT](LICENSE) © CyanYuzu。需合法安装、激活原厂 Editor 和声库。
