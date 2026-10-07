"""Search and download free music (Incompetech / Jamendo) into music/ with license + attribution."""
import json
import re
import time
import urllib.parse

import requests

from . import config
from .assets import LIBRARY, _load_library
from .media import probe_duration

INCOMPETECH_INDEX = "https://incompetech.com/music/royalty-free/pieces.json"
INCOMPETECH_DL = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
_CC_BY_4 = "http://creativecommons.org/licenses/by/4.0/"
_cache: dict = {}


def _secs(ts: str) -> int:
    parts = [int(p) for p in ts.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _incompetech(query: str, limit: int, min_seconds: int) -> list[dict]:
    if "idx" not in _cache:
        r = requests.get(INCOMPETECH_INDEX, timeout=30)
        r.raise_for_status()
        _cache["idx"] = r.json()
    words = [w for w in re.split(r"[\s,]+", query.lower()) if w]
    out = []
    for p in _cache["idx"]:
        hay = f"{p['title']} {p.get('feel') or ''} {p.get('description') or ''} {p.get('instruments') or ''}".lower()
        score = sum(w in hay for w in words)
        dur = _secs(p["length"])
        if words and score == 0 or dur < min_seconds:
            continue
        out.append((score, {
            "provider": "incompetech", "id": p["isrc"] or p["filename"], "title": p["title"],
            "artist": "Kevin MacLeod", "duration": dur, "moods": [m.strip().lower() for m in (p.get("feel") or "").split(",") if m.strip()],
            "download_url": INCOMPETECH_DL + urllib.parse.quote(p["filename"]),
            "page_url": "https://incompetech.com/music/royalty-free/music.html",
            "license": "CC BY 4.0", "license_url": _CC_BY_4,
        }))
    out.sort(key=lambda x: -x[0])
    return [o for _, o in out[:limit]]


def _jamendo(query: str, limit: int, min_seconds: int) -> list[dict]:
    if not config.JAMENDO_CLIENT_ID:
        raise RuntimeError("JAMENDO_CLIENT_ID is not set in .env")
    r = requests.get("https://api.jamendo.com/v3.0/tracks/", params={
        "client_id": config.JAMENDO_CLIENT_ID, "format": "json", "limit": 50, "search": query,
        "audiodownload_allowed": "true", "include": "musicinfo", "order": "popularity_total",
        "durationbetween": f"{min_seconds}_900",
    }, timeout=30)
    r.raise_for_status()
    out = []
    for t in r.json().get("results", []):
        lic = t.get("license_ccurl", "")
        if not lic or "-nc" in lic or "-nd" in lic:  # commercial use only, no derivatives restriction
            continue
        tags = (t.get("musicinfo") or {}).get("tags", {})
        out.append({
            "provider": "jamendo", "id": str(t["id"]), "title": t["name"], "artist": t["artist_name"],
            "duration": int(t["duration"]), "moods": (tags.get("vartags") or []) + (tags.get("genres") or []),
            "download_url": t["audiodownload"], "page_url": t.get("shareurl", ""),
            "license": "CC " + lic.rstrip("/").split("/licenses/")[-1].replace("/", " ").upper(), "license_url": lic,
        })
    return out[:limit]


def search_music(query: str, provider: str = "incompetech", limit: int = 8, min_seconds: int = 120) -> list[dict]:
    if provider == "incompetech":
        return _incompetech(query, limit, min_seconds)
    if provider == "jamendo":
        return _jamendo(query, limit, min_seconds)
    raise ValueError("provider must be incompetech or jamendo")


def attribution_text(item: dict) -> str:
    return (f'"{item["title"]}" by {item["artist"]} ({item["page_url"]}). '
            f'Licensed under {item["license"]} ({item["license_url"]})')


def download_music(item: dict, moods: list[str] | None = None) -> dict:
    sub = config.MUSIC_DIR / item["provider"]
    sub.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f'{item["title"]}-{item["id"]}')[:80]
    path = sub / f"{safe}.mp3"
    if not path.exists():
        with requests.get(item["download_url"], stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
    rel = path.relative_to(config.MUSIC_DIR).as_posix()
    lib = [t for t in _load_library() if t["file"] != rel]
    entry = {"file": rel, "title": item["title"], "moods": moods or item.get("moods", []),
             "duration": round(probe_duration(path), 1), "source": item["page_url"], "license": item["license"],
             "attribution": attribution_text(item), "downloaded_at": time.strftime("%Y-%m-%d")}
    lib.append(entry)
    LIBRARY.write_text(json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry
