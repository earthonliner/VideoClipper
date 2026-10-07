from pathlib import Path

from . import config
from .media import Cue, compose_srt, has_audio, parse_srt, probe_duration, run_ffmpeg, split_long_cues
from .project import project_dir, read_json

AUDIO_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def _video_args(fps: int) -> list[str]:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps)]


def _overlay_filter(scene: dict, clip_dir: Path, sid: str, w: int, h: int) -> str:
    text = scene.get("overlay_text")
    font = config.find_font()
    if not text or not font:
        return ""
    txt = clip_dir / f"{sid}.overlay.txt"
    txt.write_text(text, encoding="utf-8")
    size = int(h * scene.get("overlay_scale", 0.09))
    return (f",drawtext=fontfile='{font}':textfile='{txt.name}':fontsize={size}:fontcolor=white"
            f":borderw={max(2, size // 18)}:bordercolor=black@0.8:x=(w-text_w)/2:y=(h-text_h)/2")


def _build_clip(base: Path, scene: dict, w: int, h: int, fps: int, clip_dir: Path) -> tuple[Path, float]:
    sid = scene["id"]
    visual = scene.get("visual", {"type": "color", "color": "black"})
    voice = base / "audio" / f"{sid}.mp3"
    narrated = bool(scene.get("narration", "").strip())
    if narrated and not voice.exists():
        raise FileNotFoundError(f"missing voiceover for {sid}; run tts first")
    duration = (probe_duration(voice) + scene.get("pad", 0.4)) if narrated else float(scene.get("duration", 3))

    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    kind = visual.get("type", "color")
    if kind == "video":
        src = base / visual["file"]
        inputs = ["-ss", str(visual.get("start", 0)), "-stream_loop", "-1", "-i", str(src)]
        vf = f"{cover},fps={fps}"
    elif kind == "image":
        src = base / visual["file"]
        frames = int(duration * fps) + 1
        zoom = visual.get("zoom", 1.12)
        step = (zoom - 1) / frames
        inputs = ["-i", str(src)]
        vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
              f"zoompan=z='min(zoom+{step:.6f},{zoom})':d={frames}"
              f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},setsar=1")
    elif kind == "color":
        inputs = ["-f", "lavfi", "-i", f"color=c={visual.get('color', 'black')}:s={w}x{h}:r={fps}"]
        vf = "setsar=1"
    else:
        raise ValueError(f"scene {sid}: unknown visual type {kind}")
    vf += _overlay_filter(scene, clip_dir, sid, w, h) + ",format=yuv420p"

    if narrated:
        audio_in = ["-i", str(voice)]
        af = ["-af", "apad"]
    else:
        audio_in = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        af = []
    out = clip_dir / f"{sid}.mp4"
    run_ffmpeg([*inputs, *audio_in, "-map", "0:v", "-map", "1:a", "-vf", vf, *af, "-t", f"{duration:.3f}",
                *_video_args(fps), *AUDIO_ARGS, str(out)], cwd=clip_dir)
    return out, probe_duration(out)


def _bgm_path(board: dict) -> Path | None:
    bgm = board.get("bgm") or {}
    if not bgm.get("file"):
        return None
    path = config.MUSIC_DIR / bgm["file"]
    if not path.exists():
        raise FileNotFoundError(f"bgm not found: {path}")
    return path


def render(slug: str) -> dict:
    base = project_dir(slug)
    board = read_json(slug, "storyboard.json")
    w, h = board.get("resolution", config.DEFAULT_RESOLUTION)
    fps = board.get("fps", config.FPS)
    out_dir = base / "render"
    clip_dir = out_dir / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)

    cues: list[Cue] = []
    offset = 0.0
    concat_lines = []
    for scene in board["scenes"]:
        clip, dur = _build_clip(base, scene, w, h, fps, clip_dir)
        srt = base / "audio" / f"{scene['id']}.srt"
        if scene.get("subtitles", True) and srt.exists():
            cues += [Cue(c.start + offset, min(c.end, dur) + offset, c.text) for c in parse_srt(srt.read_text("utf-8"))]
        concat_lines.append(f"file '{clip.name}'")
        offset += dur
    (clip_dir / "list.txt").write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    joined = out_dir / "joined.mp4"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", str(joined)], cwd=clip_dir)
    total = probe_duration(joined)

    subs_cfg = board.get("subtitles", {"burn": True, "max_chars": 18})
    subs = out_dir / "subs.srt"
    subs.write_text(compose_srt(split_long_cues(cues, subs_cfg.get("max_chars", 18))), encoding="utf-8")

    vf = "null"
    if subs_cfg.get("burn", True) and cues:
        style = subs_cfg.get("style", f"FontName={config.SUBTITLE_FONT_NAME},FontSize=18,PrimaryColour=&H00FFFFFF,"
                                       "OutlineColour=&H80000000,BorderStyle=1,Outline=1.2,Shadow=0,MarginV=40")
        vf = f"subtitles=subs.srt:force_style='{style}'"

    bgm = _bgm_path(board)
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11"
    if bgm:
        vol = board["bgm"].get("volume", 0.15)
        fade = min(3.0, total / 4)
        inputs = ["-i", "joined.mp4", "-stream_loop", "-1", "-i", str(bgm)]
        afilter = (f"[0:a]asplit=2[v1][v2];"
                   f"[1:a]volume={vol},atrim=0:{total:.3f},afade=t=out:st={total - fade:.3f}:d={fade:.3f}[bg];"
                   f"[bg][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];"
                   f"[v2][duck]amix=inputs=2:duration=first:normalize=0,{loud}[a]")
    else:
        inputs = ["-i", "joined.mp4"]
        afilter = f"[0:a]{loud}[a]"
    final = out_dir / "final.mp4"
    run_ffmpeg([*inputs, "-filter_complex", f"[0:v]{vf}[v];{afilter}", "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                *AUDIO_ARGS, "-movflags", "+faststart", "-t", f"{total:.3f}", "final.mp4"], cwd=out_dir)
    assert has_audio(final)
    return {"final": str(final.relative_to(base)), "duration": round(probe_duration(final), 2),
            "scenes": len(board["scenes"]), "subtitles": str(subs.relative_to(base)), "bgm": bool(bgm)}


def extract_frame(slug: str, at: float, out_name: str = "frame.jpg") -> Path:
    base = project_dir(slug)
    out = base / "thumbs" / out_name
    run_ffmpeg(["-ss", str(at), "-i", str(base / "render/final.mp4"), "-frames:v", "1", "-q:v", "2", str(out)])
    return out
