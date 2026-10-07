import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from statistics import median

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY, slug TEXT, title TEXT, published_at TEXT, duration_sec INTEGER,
  features TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS stats (
  video_id TEXT, snapshot_date TEXT, days_since_publish INTEGER, views INTEGER, minutes_watched REAL,
  avg_view_duration REAL, avg_view_pct REAL, likes INTEGER, comments INTEGER, shares INTEGER,
  subs_gained INTEGER, PRIMARY KEY (video_id, snapshot_date)
);
CREATE TABLE IF NOT EXISTS changes (video_id TEXT, at TEXT, change TEXT);
"""
METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
           "likes", "comments", "shares", "subscribersGained"]


def db() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _iso_duration(text: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    d, h, mi, s = (int(x or 0) for x in m.groups()) if m else (0, 0, 0, 0)
    return d * 86400 + h * 3600 + mi * 60 + s


def register_video(slug: str, video_id: str, meta: dict) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO videos (video_id, slug, title, features) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(video_id) DO UPDATE SET slug=excluded.slug, title=excluded.title, features=excluded.features",
            (video_id, slug, meta["title"], json.dumps(meta.get("features", {}), ensure_ascii=False)))


def set_features(video_id: str, features: dict) -> None:
    with db() as conn:
        conn.execute("UPDATE videos SET features=? WHERE video_id=?", (json.dumps(features, ensure_ascii=False), video_id))


def log_change(video_id: str, change: dict) -> None:
    with db() as conn:
        conn.execute("INSERT INTO changes VALUES (?, ?, ?)",
                     (video_id, datetime.now().isoformat(timespec="seconds"), json.dumps(change, ensure_ascii=False)))


def _channel_uploads(yt, limit: int) -> list[dict]:
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    playlist = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < limit:
        page = yt.playlistItems().list(part="contentDetails", playlistId=playlist, maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in page["items"]]
        token = page.get("nextPageToken")
        if not token:
            break
    videos = []
    for i in range(0, len(ids[:limit]), 50):
        videos += yt.videos().list(part="snippet,contentDetails", id=",".join(ids[i:i + 50])).execute()["items"]
    return videos


def sync(limit: int = 200) -> dict:
    """Snapshot lifetime metrics for the channel's latest uploads. YouTube Analytics lags ~2-3 days."""
    from .youtube import analytics, youtube

    yt = youtube()
    uploads = _channel_uploads(yt, limit)
    if not uploads:
        return {"videos": 0}
    today = date.today()
    with db() as conn:
        for v in uploads:
            conn.execute(
                "INSERT INTO videos (video_id, title, published_at, duration_sec) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(video_id) DO UPDATE SET title=excluded.title, published_at=excluded.published_at, "
                "duration_sec=excluded.duration_sec",
                (v["id"], v["snippet"]["title"], v["snippet"]["publishedAt"], _iso_duration(v["contentDetails"]["duration"])))
        earliest = min(v["snippet"]["publishedAt"][:10] for v in uploads)
        published = {v["id"]: v["snippet"]["publishedAt"][:10] for v in uploads}
        rows = []
        ids = list(published)
        for i in range(0, len(ids), 200):
            resp = analytics().reports().query(
                ids="channel==MINE", startDate=earliest, endDate=today.isoformat(), metrics=",".join(METRICS),
                dimensions="video", filters="video==" + ",".join(ids[i:i + 200]), sort="-views", maxResults=200,
            ).execute()
            rows += resp.get("rows", [])
        for row in rows:
            vid, *vals = row
            age = (today - date.fromisoformat(published[vid])).days
            conn.execute("INSERT OR REPLACE INTO stats VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (vid, today.isoformat(), age, *vals))
    return {"videos": len(uploads), "with_stats": len(rows), "snapshot": today.isoformat()}


def retention(video_id: str) -> list[dict]:
    from .youtube import analytics

    resp = analytics().reports().query(
        ids="channel==MINE", startDate="2005-01-01", endDate=date.today().isoformat(),
        metrics="audienceWatchRatio,relativeRetentionPerformance", dimensions="elapsedVideoTimeRatio",
        filters=f"video=={video_id}",
    ).execute()
    return [{"at": r[0], "watch_ratio": round(r[1], 3), "relative": round(r[2], 3)} for r in resp.get("rows", [])]


def traffic_sources(video_id: str, days: int = 28) -> list[dict]:
    from .youtube import analytics

    resp = analytics().reports().query(
        ids="channel==MINE", startDate=(date.today() - timedelta(days=days)).isoformat(),
        endDate=date.today().isoformat(), metrics="views,estimatedMinutesWatched",
        dimensions="insightTrafficSourceType", filters=f"video=={video_id}", sort="-views",
    ).execute()
    return [{"source": r[0], "views": r[1], "minutes": r[2]} for r in resp.get("rows", [])]


def _latest(conn) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT v.*, s.* FROM videos v JOIN stats s ON s.video_id = v.video_id "
        "WHERE s.snapshot_date = (SELECT MAX(snapshot_date) FROM stats WHERE video_id = v.video_id)"
    ).fetchall()


def overview() -> dict:
    """All videos with features and latest metrics, plus channel medians, for pattern analysis."""
    with db() as conn:
        rows = [dict(r) for r in _latest(conn)]
    for r in rows:
        r["features"] = json.loads(r["features"] or "{}")
        r["views_per_day"] = round(r["views"] / max(r["days_since_publish"], 1), 1)
    keys = ("views_per_day", "avg_view_pct", "avg_view_duration", "subs_gained")
    medians = {k: median(r[k] for r in rows) for k in keys} if rows else {}
    return {"medians": medians, "videos": sorted(rows, key=lambda r: -r["views_per_day"])}


def report(video_id: str = "", slug: str = "") -> dict:
    with db() as conn:
        if slug and not video_id:
            row = conn.execute("SELECT video_id FROM videos WHERE slug=?", (slug,)).fetchone()
            if not row:
                raise LookupError(f"no uploaded video for project {slug}")
            video_id = row["video_id"]
        video = conn.execute("SELECT * FROM videos WHERE video_id=?", (video_id,)).fetchone()
        history = conn.execute("SELECT * FROM stats WHERE video_id=? ORDER BY snapshot_date", (video_id,)).fetchall()
        changes = conn.execute("SELECT at, change FROM changes WHERE video_id=?", (video_id,)).fetchall()
    curve = retention(video_id)
    drops = sorted(
        ({"at": f"{b['at']:.0%}", "drop": round(a["watch_ratio"] - b["watch_ratio"], 3)} for a, b in zip(curve, curve[1:])),
        key=lambda d: -d["drop"])[:5]
    return {
        "video": dict(video) if video else {"video_id": video_id},
        "history": [dict(h) for h in history],
        "retention_at": {p: next((c["watch_ratio"] for c in curve if c["at"] >= p), None) for p in (0.05, 0.25, 0.5, 0.9)},
        "biggest_drops": drops,
        "traffic_sources": traffic_sources(video_id),
        "changes": [dict(c) for c in changes],
        "channel_medians": overview()["medians"],
    }
