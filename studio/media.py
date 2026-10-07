import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"'{name}' not found on PATH; run ./setup.sh (brew install ffmpeg)")
    return path


def run_ffmpeg(args: list[str], cwd: Path | None = None) -> None:
    cmd = [require_binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-2000:]}\ncmd: {' '.join(cmd)}")


def probe(path: Path) -> dict:
    cmd = [require_binary("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def probe_duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def has_audio(path: Path) -> bool:
    return any(s["codec_type"] == "audio" for s in probe(path)["streams"])


@dataclass
class Cue:
    start: float
    end: float
    text: str


_TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def _parse_ts(ts: str) -> float:
    h, m, s, ms = _TS.match(ts.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def _fmt_ts(sec: float) -> str:
    ms = int(round(max(sec, 0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def parse_srt(text: str) -> list[Cue]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.strip().splitlines() if l.strip()]
        if len(lines) >= 2 and "-->" in lines[1]:
            start, end = lines[1].split("-->")
            cues.append(Cue(_parse_ts(start), _parse_ts(end), "\n".join(lines[2:])))
    return cues


def compose_srt(cues: list[Cue]) -> str:
    return "\n".join(f"{i}\n{_fmt_ts(c.start)} --> {_fmt_ts(c.end)}\n{c.text}\n" for i, c in enumerate(cues, 1))


_BREAK = re.compile(r"(?<=[，。！？；、,.!?;:：])")


def split_long_cues(cues: list[Cue], max_chars: int = 18) -> list[Cue]:
    """Split sentence-level cues into screen-sized chunks, distributing time by character count."""
    out = []
    for cue in cues:
        text = cue.text.replace("\n", "")
        if len(text) <= max_chars:
            out.append(Cue(cue.start, cue.end, text.strip(" ，,。")))
            continue
        parts, buf = [], ""
        for piece in filter(None, _BREAK.split(text)):
            while len(piece) > max_chars:
                if buf:
                    parts.append(buf)
                    buf = ""
                parts.append(piece[:max_chars])
                piece = piece[max_chars:]
            if len(buf) + len(piece) > max_chars and buf:
                parts.append(buf)
                buf = ""
            buf += piece
        if buf:
            parts.append(buf)
        total = sum(len(p) for p in parts)
        t = cue.start
        for p in parts:
            dur = (cue.end - cue.start) * len(p) / total
            out.append(Cue(t, t + dur, p.strip(" ，,。")))
            t += dur
    return out
