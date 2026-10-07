import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from . import config

GATES = ("topic", "script", "final_cut", "publish")

# Files whose content is fingerprinted at approval time; editing them afterwards voids the approval.
GATE_FILES = {
    "topic": ["brief.md"],
    "script": ["script.md"],
    "final_cut": ["render/final.mp4"],
    "publish": ["publish.json"],
}


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text.strip().lower()).strip("-")
    return text[:40] or "untitled"


def project_dir(slug: str) -> Path:
    path = config.PROJECTS_DIR / slug
    if not path.is_dir():
        raise FileNotFoundError(f"project not found: {slug}")
    return path


def create_project(topic: str) -> dict:
    slug = f"{datetime.now():%Y%m%d}-{slugify(topic)}"
    path = config.PROJECTS_DIR / slug
    if path.exists():
        raise FileExistsError(f"project already exists: {slug}")
    for sub in ("assets", "audio", "render", "thumbs"):
        (path / sub).mkdir(parents=True)
    for name in ("brief.md", "script.md", "storyboard.json", "publish.json"):
        src = config.TEMPLATES_DIR / name
        if src.exists():
            shutil.copy(src, path / name)
    (path / "licenses.json").write_text("[]\n", encoding="utf-8")
    state = {
        "slug": slug,
        "topic": topic,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "approvals": {},
        "youtube": {},
    }
    save_state(slug, state, base=path)
    return state


def list_projects() -> list[dict]:
    if not config.PROJECTS_DIR.exists():
        return []
    out = []
    for path in sorted(config.PROJECTS_DIR.iterdir()):
        if (path / "state.json").exists():
            st = load_state(path.name)
            out.append({"slug": st["slug"], "topic": st["topic"], "approved": sorted(st["approvals"])})
    return out


def load_state(slug: str) -> dict:
    return json.loads((project_dir(slug) / "state.json").read_text(encoding="utf-8"))


def save_state(slug: str, state: dict, base: Path | None = None) -> None:
    base = base or project_dir(slug)
    (base / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _fingerprint(slug: str, gate: str) -> str:
    base = project_dir(slug)
    digest = hashlib.sha256()
    for rel in GATE_FILES[gate]:
        path = base / rel
        if not path.exists():
            raise FileNotFoundError(f"cannot approve '{gate}': missing {rel}")
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def approve(slug: str, gate: str, note: str = "") -> dict:
    if gate not in GATES:
        raise ValueError(f"unknown gate {gate}; expected one of {GATES}")
    state = load_state(slug)
    state["approvals"][gate] = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "sha256": _fingerprint(slug, gate),
    }
    save_state(slug, state)
    return state["approvals"][gate]


def check_approval(slug: str, gate: str) -> tuple[bool, str]:
    record = load_state(slug)["approvals"].get(gate)
    if not record:
        return False, f"'{gate}' has not been approved by the user"
    try:
        current = _fingerprint(slug, gate)
    except FileNotFoundError as exc:
        return False, str(exc)
    if current != record["sha256"]:
        return False, f"files for '{gate}' changed after approval; ask the user to re-approve"
    return True, "ok"


def require_approval(slug: str, *gates: str) -> None:
    problems = [msg for ok, msg in (check_approval(slug, g) for g in gates) if not ok]
    if problems:
        raise PermissionError("; ".join(problems))


def status(slug: str) -> dict:
    state = load_state(slug)
    base = project_dir(slug)
    return {
        "slug": slug,
        "topic": state["topic"],
        "gates": {g: check_approval(slug, g)[1] for g in GATES},
        "files": {
            "voice_clips": len(list((base / "audio").glob("*.mp3"))),
            "assets": len([p for p in (base / "assets").iterdir() if p.is_file()]),
            "final_cut": (base / "render/final.mp4").exists(),
            "thumbnails": sorted(p.name for p in (base / "thumbs").glob("*.jpg")),
        },
        "youtube": state.get("youtube", {}),
    }


def read_json(slug: str, name: str) -> dict:
    return json.loads((project_dir(slug) / name).read_text(encoding="utf-8"))
