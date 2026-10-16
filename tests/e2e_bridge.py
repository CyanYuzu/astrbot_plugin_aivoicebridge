"""Opt-in test of real plugin methods + real HTTP bridge + licensed Editor.

Only AstrBot registration/event objects are test doubles; HTTP and synthesis are real.
Run against an isolated bridge config because this test changes persistent defaults.
"""
import argparse
import asyncio
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_main import _FakeEvent, main as plugin_module  # AstrBot import-only stubs


async def run(base):
    async with httpx.AsyncClient(base_url=base, timeout=180) as client:
        response = await client.get("/voices")
        response.raise_for_status()
        voice = next(v for v in response.json()["voices"] if v["available"])
        baseline = (await client.get("/config")).json()
        plugin = plugin_module.AIVoiceBridgePlugin(None, {
            "api_base": base, "engine": "aivoice2", "voice": voice["id"], "speed": 1.25,
            "pitch": 1.1, "pitch_range": .8, "volume": .9,
            "language": "standard", "styles": json.dumps({voice["styles"][0]: .2}),
            "middle_pause": 150, "long_pause": 370, "sentence_pause": 800,
        })
        try:
            await plugin.initialize()
            actual = await plugin._get_config()
            assert actual["speed"] == 1.25 and actual["voice"] == voice["id"]
            assert not any(key in actual for key in plugin_module.PAUSE_KEYS)
            for action in ["push", "status", "voices", "health", "parameters"]:
                messages = [message async for message in plugin.aivoice(_FakeEvent(f"/aivoice {action}"))]
                assert len(messages) == 1 and "❌" not in messages[0], messages
            response = await client.get("/tts", params={"text": "アストラボットの音声接続テストです。", "text_lang": "auto"})
            response.raise_for_status()
            with wave.open(io.BytesIO(response.content)) as wav:
                assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (48000, 1, 2)
                assert wav.getnframes() > 0
                seconds = wav.getnframes() / wav.getframerate()
            return {"passed": True, "engine": actual["engine"], "voice": voice["id"],
                    "commands_tested": ["push", "status", "voices", "health", "parameters"],
                    "wav_bytes": len(response.content), "wav_seconds": seconds,
                    "wav_sha256": hashlib.sha256(response.content).hexdigest(),
                    "plugin_http_calls_real": True, "synthesis_real": True,
                    "astrbot_registration_stubbed": True, "remote_bot_message_delivery_tested": False}
        finally:
            now = (await client.get("/config")).json()
            restore = {key: None for key in now if key not in baseline and key != "engine"}
            restore.update(baseline)
            response = await client.post("/config", json=restore)
            response.raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:19765")
    parser.add_argument("--output", type=Path, default=Path("evidence/e2e-plugin-v2.json"))
    args = parser.parse_args()
    summary = asyncio.run(run(args.api_base.rstrip("/")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
