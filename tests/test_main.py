"""astrbot_plugin_aivoicebridge 插件单元测试。

AstrBot 运行环境在本地不可用, 因此在导入 main 之前注入假的 astrbot.api 模块,
以隔离测试插件的核心逻辑 (配置构造 / HTTP 推送 / 指令处理)。
"""

import asyncio
import sys
import types
from unittest import mock

import httpx

# ---------------------------------------------------------------------------
# 注入假的 astrbot 模块 (必须在 import main 之前)
# ---------------------------------------------------------------------------


def _identity_decorator(*_args, **_kwargs):
    """返回一个原样返回被装饰对象的装饰器, 以绕过 AstrBot 的注册装饰器。"""

    def deco(obj):
        return obj

    return deco


class _FakeFilter:
    """假的 filter, 让 @filter.command(...) 原样返回处理函数。"""

    @staticmethod
    def command(*args, **kwargs):
        return _identity_decorator()


class _FakeEvent:
    """假的 AstrMessageEvent, 只实现测试需要的最小接口。"""

    def __init__(self, message_str: str):
        self.message_str = message_str

    def plain_result(self, text: str):
        return text


_astrbot = types.ModuleType("astrbot")
_astrbot_api = types.ModuleType("astrbot.api")
_astrbot_api.AstrBotConfig = dict
_astrbot_api.logger = mock.MagicMock()
_astrbot_api.event = types.ModuleType("astrbot.api.event")
_astrbot_api.event.AstrMessageEvent = object
_astrbot_api.event.filter = _FakeFilter()
_astrbot_api.star = types.ModuleType("astrbot.api.star")
_astrbot_api.star.Context = object


class _FakeStar:
    """假的 Star 基类, 接受任意初始化参数。"""

    def __init__(self, *args, **kwargs):
        pass


_astrbot_api.star.Star = _FakeStar
_astrbot_api.star.register = _identity_decorator

sys.modules["astrbot"] = _astrbot
sys.modules["astrbot.api"] = _astrbot_api
sys.modules["astrbot.api.event"] = _astrbot_api.event
sys.modules["astrbot.api.star"] = _astrbot_api.star

import main


def make_plugin(config: dict | None = None):
    """构造插件实例, 默认给一套完整配置。"""
    cfg = (
        config
        if config is not None
        else {
            "api_base": "http://127.0.0.1:18765/",
            "voice": "紲星 あかり（蕾）",
            "volume": 1.0,
            "speed": 1.2,
            "pitch": 1.1,
            "pitch_range": 1.3,
            "middle_pause": 200,
            "long_pause": 500,
            "sentence_pause": 900,
            "auto_push": True,
        }
    )
    return main.AIVoiceBridgePlugin(context=None, config=cfg)


def run(coro):
    """在事件循环中执行一个协程并返回结果。"""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _base_url / _payload / _format
# ---------------------------------------------------------------------------


def test_base_url_default():
    p = main.AIVoiceBridgePlugin(context=None, config={})
    assert p._base_url() == main.DEFAULT_API_BASE


def test_base_url_custom_and_trailing_slash():
    p = main.AIVoiceBridgePlugin(
        context=None, config={"api_base": "http://1.2.3.4:9999/"}
    )
    assert p._base_url() == "http://1.2.3.4:9999"


def test_payload_skips_empty_values():
    cfg = {
        "voice": "琴葉 茜（Chinese）",
        "volume": 1.5,
        "speed": "",  # 空字符串 → 跳过
        "pitch": None,  # None → 跳过
        "pitch_range": 1.3,
        "middle_pause": 0,  # 0 是合法值, 不应跳过
        "long_pause": 500,
        "sentence_pause": 900,
    }
    payload = make_plugin(cfg)._payload()
    assert payload == {
        "voice": "琴葉 茜（Chinese）",
        "volume": 1.5,
        "pitch_range": 1.3,
        "middle_pause": 0,
        "long_pause": 500,
        "sentence_pause": 900,
    }
    assert "speed" not in payload
    assert "pitch" not in payload


def test_payload_without_voice():
    p = make_plugin({})
    assert p._payload() == {}


def test_format_lines_and_empty():
    assert main.AIVoiceBridgePlugin._format({"a": 1, "b": "x"}) == "  a: 1\n  b: x"
    assert main.AIVoiceBridgePlugin._format({}) == "  (空)"


# ---------------------------------------------------------------------------
# HTTP 推送 / 读取 (mock httpx.AsyncClient)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=None
            )

    def json(self):
        return self._data


class _FakeAsyncClient:
    """假的 httpx.AsyncClient, 支持 async with 并记录调用。"""

    def __init__(self, resp):
        self.resp = resp
        self.post_calls = []  # [(url, json)]
        self.get_calls = []  # [url]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None):
        self.post_calls.append((url, json))
        return self.resp

    async def get(self, url):
        self.get_calls.append(url)
        return self.resp


def _patch_client(resp):
    """替换 main.httpx.AsyncClient, 返回假客户端以便断言。"""
    client = _FakeAsyncClient(resp)
    return mock.patch("main.httpx.AsyncClient", return_value=client), client


def test_post_config_uses_base_and_payload():
    p = make_plugin()
    fake_resp = _FakeResponse({"voice": "紲星 あかり（蕾）", "volume": 1.0})
    patcher, client = _patch_client(fake_resp)
    with patcher:
        result = run(p._post_config())

    assert result == fake_resp.json()
    # 验证请求 URL 与请求体
    assert client.post_calls == [("http://127.0.0.1:18765/config", p._payload())]


def test_post_config_raises_on_http_error():
    p = make_plugin()
    patcher, _ = _patch_client(_FakeResponse({"error": "bad"}, status_code=500))
    with patcher:
        try:
            run(p._post_config())
            raised = False
        except httpx.HTTPStatusError:
            raised = True
    assert raised


def test_get_config():
    p = make_plugin()
    fake_resp = _FakeResponse({"voice": "琴葉 茜（Chinese）"})
    patcher, client = _patch_client(fake_resp)
    with patcher:
        result = run(p._get_config())

    assert result == {"voice": "琴葉 茜（Chinese）"}
    assert client.get_calls == ["http://127.0.0.1:18765/config"]


# ---------------------------------------------------------------------------
# 指令 /aivoice
# ---------------------------------------------------------------------------


def collect_results(agen):
    """收集 async generator handler 产出的结果。"""
    return [r for r in run(_collect(agen))]


async def _collect(agen):
    return [x async for x in agen]


def test_command_status():
    p = make_plugin()
    fake_resp = _FakeResponse({"voice": "紲星 あかり（蕾）", "volume": 1.5})
    patcher, _ = _patch_client(fake_resp)
    with patcher:
        results = collect_results(p.aivoice(_FakeEvent("aivoice status")))
    assert len(results) == 1
    assert "紲星 あかり（蕾）" in results[0]
    assert "volume" in results[0]


def test_command_push():
    p = make_plugin()
    fake_resp = _FakeResponse({"voice": "紲星 あかり（蕾）", "speed": 1.2})
    patcher, client = _patch_client(fake_resp)
    with patcher:
        results = collect_results(p.aivoice(_FakeEvent("aivoice push")))
    assert "✅" in results[0]
    assert len(client.post_calls) == 1


def test_command_without_prefix_works():
    """兼容 message_str 不带指令前缀 (如只传 'status') 的情况。"""
    p = make_plugin()
    fake_resp = _FakeResponse({"voice": "紲星 あかり（蕾）"})
    patcher, _ = _patch_client(fake_resp)
    with patcher:
        results = collect_results(p.aivoice(_FakeEvent("status")))
    assert len(results) == 1


def test_command_unknown_action():
    p = make_plugin()
    results = collect_results(p.aivoice(_FakeEvent("aivoice foo")))
    assert "用法" in results[0]


def test_command_error_is_caught():
    """桥接不可达等异常应被捕获并返回提示, 而不是崩溃。"""
    p = make_plugin()
    patcher, _ = _patch_client(_FakeResponse({"error": "boom"}, status_code=500))
    with patcher:
        results = collect_results(p.aivoice(_FakeEvent("aivoice push")))
    assert "❌" in results[0]


def test_initialize_pushes_when_auto_push():
    p = make_plugin()
    fake_resp = _FakeResponse({"voice": "紲星 あかり（蕾）"})
    patcher, client = _patch_client(fake_resp)
    with patcher:
        run(p.initialize())
    assert len(client.post_calls) == 1


def test_initialize_skips_when_auto_push_false():
    p = make_plugin({"auto_push": False})
    patcher, client = _patch_client(_FakeResponse({}))
    with patcher:
        run(p.initialize())
    assert client.post_calls == []
