import json
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config
from .media import probe_duration
from .project import project_dir

TIMEOUT = 30


def _pick_pexels_file(files: list[dict], min_width: int) -> dict | None:
    mp4 = [f for f in files if f.get("file_type") == "video/mp4" and f.get("width")]
    good = sorted((f for f in mp4 if f["width"] >= min_width), key=lambda f: f["width"])
    return (good or sorted(mp4, key=lambda f: -f["width"]) or [None])[0]


def _pexels(query: str, kind: str, per_page: int, orientation: str) -> list[dict]:
    if not config.PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY is not set in .env")
    headers = {"Authorization": config.PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    if kind == "video":
        data = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=TIMEOUT)
        data.raise_for_status()
        out = []
        for v in data.json().get("videos", []):
            f = _pick_pexels_file(v.get("video_files", []), 1920)
            if f:
                out.append({
                    "provider": "pexels", "kind": "video", "id": str(v["id"]), "download_url": f["link"],
                    "page_url": v["url"], "author": v.get("user", {}).get("name", ""),
                    "width": f["width"], "height": f["height"], "duration": v.get("duration"),
                    "preview": v.get("image"),
                })
        return out
    data = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=TIMEOUT)
    data.raise_for_status()
    return [{
        "provider": "pexels", "kind": "image", "id": str(p["id"]), "download_url": p["src"]["original"],
        "page_url": p["url"], "author": p.get("photographer", ""), "width": p["width"], "height": p["height"],
        "preview": p["src"].get("medium"), "alt": p.get("alt", ""),
    } for p in data.json().get("photos", [])]


def _pixabay(query: str, kind: str, per_page: int, orientation: str) -> list[dict]:
    if not config.PIXABAY_API_KEY:
        raise RuntimeError("PIXABAY_API_KEY is not set in .env")
    params = {"key": config.PIXABAY_API_KEY, "q": query[:100], "per_page": max(3, min(per_page, 200)), "safesearch": "true"}
    if kind == "video":
        resp = requests.get("https://pixabay.com/api/videos/", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        out = []
        for h in resp.json().get("hits", []):
            vids = h.get("videos", {})
            f = next((vids[k] for k in ("large", "medium", "small") if vids.get(k, {}).get("url")), None)
            if f:
                out.append({
                    "provider": "pixabay", "kind": "video", "id": str(h["id"]), "download_url": f["url"],
                    "page_url": h["pageURL"], "author": h.get("user", ""), "width": f.get("width"),
                    "height": f.get("height"), "duration": h.get("duration"), "preview": f.get("thumbnail"),
                    "tags": h.get("tags", ""),
                })
        return out
    params.update({"image_type": "photo", "orientation": "horizontal" if orientation == "landscape" else "vertical"})
    resp = requests.get("https://pixabay.com/api/", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return [{
        "provider": "pixabay", "kind": "image", "id": str(h["id"]), "download_url": h["largeImageURL"],
        "page_url": h["pageURL"], "author": h.get("user", ""), "width": h.get("imageWidth"),
        "height": h.get("imageHeight"), "preview": h.get("previewURL"), "tags": h.get("tags", ""),
    } for h in resp.json().get("hits", [])]


def search_stock(query: str, kind: str = "video", provider: str = "pexels", per_page: int = 8,
                 orientation: str = "landscape") -> list[dict]:
    if kind not in ("video", "image"):
        raise ValueError("kind must be 'video' or 'image'")
    fn = {"pexels": _pexels, "pixabay": _pixabay}.get(provider)
    if not fn:
        raise ValueError("provider must be 'pexels' or 'pixabay'")
    return fn(query, kind, per_page, orientation)


LICENSE_TEXT = {
    "pexels": "Pexels License (free commercial use, no attribution required)",
    "pixabay": "Pixabay Content License (free commercial use, no attribution required)",
}


def download_asset(slug: str, scene_id: str, item: dict) -> dict:
    base = project_dir(slug)
    ext = Path(urlparse(item["download_url"]).path).suffix or (".mp4" if item["kind"] == "video" else ".jpg")
    dest = base / "assets" / f"{scene_id}-{item['provider']}-{item['id']}{ext.lower()}"
    if not dest.exists():
        with requests.get(item["download_url"], stream=True, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as fh:
                for chunk in resp.iter_content(1 << 20):
                    fh.write(chunk)
            tmp.rename(dest)
    record = {
        "file": f"assets/{dest.name}", "scene_id": scene_id, "provider": item["provider"], "id": item["id"],
        "page_url": item["page_url"], "author": item.get("author", ""),
        "license": LICENSE_TEXT.get(item["provider"], item.get("license", "unknown")),
    }
    _append_license(base, record)
    return record


def register_local_asset(slug: str, scene_id: str, file: str, source: str, license: str) -> dict:
    """Record provenance for a file the user supplied or generated locally (e.g. ComfyUI)."""
    base = project_dir(slug)
    if not (base / file).exists():
        raise FileNotFoundError(file)
    record = {"file": file, "scene_id": scene_id, "provider": "local", "page_url": source, "author": "", "license": license}
    _append_license(base, record)
    return record


def _append_license(base: Path, record: dict) -> None:
    path = base / "licenses.json"
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    items = [i for i in items if i["file"] != record["file"]] + [record]
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ---- music library -------------------------------------------------------

LIBRARY = config.MUSIC_DIR / "library.json"
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


def _load_library() -> list[dict]:
    return json.loads(LIBRARY.read_text(encoding="utf-8")) if LIBRARY.exists() else []


def scan_music() -> dict:
    """Add newly dropped files in music/ to library.json; moods/license are filled in afterwards."""
    lib = _load_library()
    known = {t["file"] for t in lib}
    added = []
    for path in sorted(config.MUSIC_DIR.rglob("*")):
        rel = path.relative_to(config.MUSIC_DIR).as_posix()
        if path.suffix.lower() in AUDIO_EXT and rel not in known:
            entry = {"file": rel, "title": path.stem, "moods": [], "duration": round(probe_duration(path), 1),
                     "source": "", "license": ""}
            lib.append(entry)
            added.append(rel)
    lib = [t for t in lib if (config.MUSIC_DIR / t["file"]).exists()]
    LIBRARY.write_text(json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"added": added, "total": len(lib), "untagged": [t["file"] for t in lib if not t["moods"]]}


def tag_music(file: str, moods: list[str], source: str = "", license: str = "") -> dict:
    lib = _load_library()
    for t in lib:
        if t["file"] == file:
            t["moods"] = moods
            t["source"] = source or t["source"]
            t["license"] = license or t["license"]
            LIBRARY.write_text(json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8")
            return t
    raise FileNotFoundError(f"{file} not in library; run music scan first")


def list_music(mood: str = "") -> list[dict]:
    lib = _load_library()
    return [t for t in lib if not mood or mood.lower() in (m.lower() for m in t["moods"])]
