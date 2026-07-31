"""AstrBot 插件: AIVoice Bridge 参数控制

自动 TTS 由 AstrBot 内置的 GSV TTS provider (gsv_tts_selfhost) 完成,
但它只会向本地桥接发送 text, 无法传递音色/音量/话速等参数。

本插件把这些参数推送到本地桥接服务的 /config 接口 (GET/POST),
桥接会将其持久化为"默认参数"。此后 GSV provider 每次无参调用 /tts 时,
合成使用的就是这份默认参数, 从而实现在 AIVoice 作为 TTS 源时调整其参数。

指令:
  /aivoice status  -> 查看桥接当前生效的默认参数
  /aivoice push    -> 将插件配置推送到桥接, 使改动立即生效
"""

import json

import httpx
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

# 与桥接 /tts 及 /config 接口对应的参数键 (A.I.VOICE MasterControl)
PARAM_KEYS: tuple[str, ...] = (
    "volume",  # 音量 0.00 ~ 5.00
    "speed",  # 话速 0.50 ~ 4.00
    "pitch",  # 声调高低 0.50 ~ 2.00
    "pitch_range",  # 抑扬/强调程度 0.00 ~ 2.00 (可写作 emphasis)
    "middle_pause",  # 句中短停顿 ms 80 ~ 500 (仅日语声库)
    "long_pause",  # 句中长停顿 ms 80 ~ 2000 (仅日语声库)
    "sentence_pause",  # 句末停顿 ms 0 ~ 10000 (仅日语声库)
)

DEFAULT_API_BASE = "http://127.0.0.1:18765"


@register(
    "astrbot_plugin_aivoicebridge",
    "AIVoiceBridge",
    "A.I.VOICE 桥接 TTS 参数控制",
    "1.0.0",
)
class AIVoiceBridgePlugin(Star):
    """AIVoice 桥接参数控制插件。"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config if config is not None else {}
        self.http_timeout = 10

    # ---- 内部工具 ----
    def _base_url(self) -> str:
        """桥接服务根地址, 去除末尾斜杠。"""
        url = self.config.get("api_base") or DEFAULT_API_BASE
        return str(url).rstrip("/")

    def _payload(self) -> dict:
        """根据插件配置构造推送到桥接 /config 的 JSON, 跳过空值。"""
        cfg = self.config
        payload: dict = {}
        if cfg.get("voice"):
            payload["voice"] = cfg["voice"]
        for key in PARAM_KEYS:
            val = cfg.get(key)
            if val is not None and val != "":
                payload[key] = val
        return payload

    async def _post_config(self) -> dict:
        """推送配置到桥接 /config, 返回桥接生效的最新配置。"""
        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            resp = await client.post(f"{self._base_url()}/config", json=self._payload())
            resp.raise_for_status()
            return resp.json()

    async def _get_config(self) -> dict:
        """读取桥接当前生效的默认参数。"""
        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            resp = await client.get(f"{self._base_url()}/config")
            resp.raise_for_status()
            return resp.json()

    # ---- 生命周期 ----
    async def initialize(self):
        """插件加载完成后自动推送一次配置 (可通过 auto_push 配置关闭)。"""
        if self.config.get("auto_push", True):
            try:
                result = await self._post_config()
                logger.info(
                    "[AIVoiceBridge] 已自动推送配置: "
                    f"{json.dumps(result, ensure_ascii=False)}"
                )
            except Exception as e:  # noqa: BLE001 - 插件容错, 不允许异常导致崩溃
                logger.error(f"[AIVoiceBridge] 初始化推送配置失败: {e}")

    # ---- 指令 ----
    @filter.command("aivoice")
    async def aivoice(self, event: AstrMessageEvent):
        """AIVoice 桥接参数控制, 用法: /aivoice [push|status]"""
        args = event.message_str.strip().split()
        # 兼容 message_str 带/不带指令前缀两种情况
        if args and args[0].lstrip("/").lower() == "aivoice":
            args = args[1:]
        action = args[0].lower() if args else "status"

        try:
            if action == "push":
                result = await self._post_config()
                yield event.plain_result(
                    "✅ 已推送配置到 AIVoice 桥接\n" + self._format(result)
                )
            elif action == "status":
                result = await self._get_config()
                yield event.plain_result("桥接当前默认参数:\n" + self._format(result))
            else:
                yield event.plain_result("用法: /aivoice [push|status]")
        except Exception as e:  # noqa: BLE001 - 插件容错, 不允许异常导致崩溃
            logger.error(f"[AIVoiceBridge] 指令执行失败: {e}")
            yield event.plain_result(f"❌ 操作失败: {e}")

    @staticmethod
    def _format(d: dict) -> str:
        """把参数字典格式化为多行文本。"""
        lines = [f"  {k}: {v}" for k, v in d.items()]
        return "\n".join(lines) if lines else "  (空)"
