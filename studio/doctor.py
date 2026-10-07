import shutil
import subprocess

from . import config


def run() -> dict:
    checks = {}
    for binary in ("ffmpeg", "ffprobe"):
        checks[binary] = bool(shutil.which(binary))
    if checks["ffmpeg"]:
        filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        checks["ffmpeg_libass(subtitles)"] = " subtitles " in filters
        checks["ffmpeg_drawtext"] = " drawtext " in filters
    checks["font"] = config.find_font() or False
    checks["PEXELS_API_KEY"] = bool(config.PEXELS_API_KEY)
    checks["PIXABAY_API_KEY"] = bool(config.PIXABAY_API_KEY)
    checks["youtube_client_secret"] = (config.SECRETS_DIR / "client_secret.json").exists()
    checks["youtube_token"] = (config.SECRETS_DIR / "token.json").exists()
    try:
        import mlx_whisper  # noqa: F401
        checks["mlx_whisper"] = True
    except ImportError:
        checks["mlx_whisper"] = "optional, not installed"
    return checks
