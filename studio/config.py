import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(os.environ.get("STUDIO_ROOT", Path(__file__).resolve().parent.parent))
load_dotenv(ROOT / ".env")

PROJECTS_DIR = ROOT / "projects"
KNOWLEDGE_DIR = ROOT / "knowledge"
MUSIC_DIR = ROOT / "music"
SECRETS_DIR = ROOT / ".secrets"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "studio.db"
TEMPLATES_DIR = ROOT / "templates"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")

DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "en-US-AndrewNeural")
DEFAULT_RESOLUTION = tuple(int(x) for x in os.environ.get("DEFAULT_RESOLUTION", "1920x1080").split("x"))
FPS = int(os.environ.get("FPS", "30"))

FONT_CANDIDATES = [
    os.environ.get("STUDIO_FONT", ""),
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
SUBTITLE_FONT_NAME = os.environ.get("SUBTITLE_FONT_NAME", "PingFang SC")


def find_font() -> str | None:
    for path in FONT_CANDIDATES:
        if path and Path(path).exists():
            return path
    return None
