import asyncio
import hashlib

import edge_tts

from . import config
from .media import probe_duration
from .project import project_dir, read_json


async def _synth(text: str, voice: str, rate: str, pitch: str, mp3, srt) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="SentenceBoundary")
    sub = edge_tts.SubMaker()
    with open(mp3, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                sub.feed(chunk)
    srt.write_text(sub.get_srt(), encoding="utf-8")


def generate_voiceover(slug: str, force: bool = False) -> list[dict]:
    """Synthesize narration for every storyboard scene. Unchanged scenes are skipped unless force=True."""
    base = project_dir(slug)
    board = read_json(slug, "storyboard.json")
    voice = board.get("voice", config.DEFAULT_VOICE)
    rate = board.get("voice_rate", "+0%")
    pitch = board.get("voice_pitch", "+0Hz")
    results = []
    for scene in board["scenes"]:
        text = scene.get("narration", "").strip()
        if not text:
            continue
        sid = scene["id"]
        s_voice, s_rate = scene.get("voice", voice), scene.get("voice_rate", rate)
        mp3, srt, stamp = (base / "audio" / f"{sid}{ext}" for ext in (".mp3", ".srt", ".hash"))
        key = hashlib.sha256(f"{s_voice}|{s_rate}|{pitch}|{text}".encode()).hexdigest()
        if force or not mp3.exists() or not stamp.exists() or stamp.read_text() != key:
            asyncio.run(_synth(text, s_voice, s_rate, pitch, mp3, srt))
            stamp.write_text(key)
            state = "generated"
        else:
            state = "cached"
        results.append({"scene": sid, "status": state, "duration": round(probe_duration(mp3), 2)})
    return results


def list_voices(locale_prefix: str = "zh-") -> list[dict]:
    voices = asyncio.run(edge_tts.list_voices())
    return [
        {"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"],
         "styles": v.get("VoiceTag", {}).get("VoicePersonalities", [])}
        for v in voices if v["Locale"].lower().startswith(locale_prefix.lower())
    ]


def transcribe(audio_path: str, language: str = "zh") -> str:
    """Local Whisper transcription (Apple Silicon) for user-recorded narration; returns SRT text."""
    try:
        import mlx_whisper
    except ImportError as exc:
        raise RuntimeError("mlx-whisper not installed; run: .venv/bin/pip install -e '.[mac]'") from exc
    from .media import Cue, compose_srt

    result = mlx_whisper.transcribe(audio_path, language=language,
                                    path_or_hf_repo="mlx-community/whisper-large-v3-turbo")
    return compose_srt([Cue(s["start"], s["end"], s["text"].strip()) for s in result["segments"]])
