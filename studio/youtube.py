import random
import socket
import time
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config
from .project import load_state, project_dir, read_json, require_approval, save_state

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
CLIENT_SECRET = config.SECRETS_DIR / "client_secret.json"
TOKEN = config.SECRETS_DIR / "token.json"
RETRYABLE_STATUS = {500, 502, 503, 504}


def credentials(interactive: bool = False) -> Credentials:
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise PermissionError("YouTube not authorized; run `studio auth` in a terminal first")
        if not CLIENT_SECRET.exists():
            raise FileNotFoundError(f"put your OAuth desktop client JSON at {CLIENT_SECRET}")
        creds = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES).run_local_server(port=0)
    config.SECRETS_DIR.mkdir(exist_ok=True)
    TOKEN.write_text(creds.to_json())
    TOKEN.chmod(0o600)
    return creds


def youtube():
    return build("youtube", "v3", credentials=credentials(), cache_discovery=False)


def analytics():
    return build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)


def search_videos(query: str, max_results: int = 10, order: str = "relevance", region: str = "",
                  language: str = "", published_after_days: int = 0) -> list[dict]:
    """Costs 100 quota units per call (+1 for statistics); prefer web search for broad exploration."""
    yt = youtube()
    params = {"q": query, "part": "snippet", "type": "video", "maxResults": min(max_results, 50), "order": order}
    if region:
        params["regionCode"] = region
    if language:
        params["relevanceLanguage"] = language
    if published_after_days:
        after = datetime.now(timezone.utc).timestamp() - published_after_days * 86400
        params["publishedAfter"] = datetime.fromtimestamp(after, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = yt.search().list(**params).execute().get("items", [])
    ids = [i["id"]["videoId"] for i in items]
    if not ids:
        return []
    details = yt.videos().list(part="statistics,contentDetails,snippet", id=",".join(ids)).execute()["items"]
    return [{
        "video_id": v["id"], "title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
        "published_at": v["snippet"]["publishedAt"], "duration": v["contentDetails"]["duration"],
        "views": int(v["statistics"].get("viewCount", 0)), "likes": int(v["statistics"].get("likeCount", 0)),
        "comments": int(v["statistics"].get("commentCount", 0)), "tags": v["snippet"].get("tags", [])[:15],
        "url": f"https://youtu.be/{v['id']}",
    } for v in details]


def validate_publish(slug: str) -> list[str]:
    meta = read_json(slug, "publish.json")
    base = project_dir(slug)
    errors = []
    title = meta.get("title", "")
    if not title or len(title) > 100:
        errors.append("title must be 1-100 characters")
    if len(meta.get("description", "").encode("utf-8")) > 5000:
        errors.append("description exceeds 5000 bytes")
    for field in ("title", "description"):
        if any(c in meta.get(field, "") for c in "<>"):
            errors.append(f"{field} must not contain '<' or '>'")
    tags = meta.get("tags", [])
    if sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0) > 500:
        errors.append("tags exceed 500 characters total")
    if meta.get("privacyStatus") not in ("private", "unlisted", "public"):
        errors.append("privacyStatus must be private, unlisted or public")
    if meta.get("publishAt") and meta.get("privacyStatus") != "private":
        errors.append("publishAt requires privacyStatus=private")
    thumb = meta.get("thumbnail")
    if thumb and not (base / thumb).exists():
        errors.append(f"thumbnail not found: {thumb}")
    if not (base / "render/final.mp4").exists():
        errors.append("render/final.mp4 not found")
    return errors


def _resumable(request, label: str):
    response, retries = None, 0
    while response is None:
        try:
            _, response = request.next_chunk()
            retries = 0
        except HttpError as exc:
            if exc.resp.status not in RETRYABLE_STATUS:
                raise
            err = exc
        except (OSError, socket.timeout) as exc:
            err = exc
        else:
            continue
        retries += 1
        if retries > 8:
            raise RuntimeError(f"{label}: giving up after repeated errors: {err}")
        time.sleep(min(2 ** retries, 64) + random.random())
    return response


def upload(slug: str) -> dict:
    """Upload render/final.mp4 with publish.json metadata. Requires user approval of final_cut and publish."""
    require_approval(slug, "final_cut", "publish")
    errors = validate_publish(slug)
    if errors:
        raise ValueError("; ".join(errors))
    state = load_state(slug)
    if state.get("youtube", {}).get("video_id"):
        raise RuntimeError(f"already uploaded as {state['youtube']['video_id']}")
    base = project_dir(slug)
    meta = read_json(slug, "publish.json")
    lang = meta.get("defaultLanguage", "en")
    body = {
        "snippet": {
            "title": meta["title"], "description": meta.get("description", ""), "tags": meta.get("tags", []),
            "categoryId": str(meta.get("categoryId", "27")), "defaultLanguage": lang,
            "defaultAudioLanguage": meta.get("defaultAudioLanguage", lang),
        },
        "status": {
            "privacyStatus": meta["privacyStatus"],
            "selfDeclaredMadeForKids": bool(meta.get("madeForKids", False)),
            "containsSyntheticMedia": bool(meta.get("containsSyntheticMedia", True)),
        },
    }
    if meta.get("publishAt"):
        body["status"]["publishAt"] = meta["publishAt"]
    yt = youtube()
    media = MediaFileUpload(str(base / "render/final.mp4"), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    response = _resumable(yt.videos().insert(part="snippet,status", body=body, media_body=media), "upload")
    video_id = response["id"]
    state["youtube"] = {"video_id": video_id, "uploaded_at": datetime.now().isoformat(timespec="seconds"),
                        "url": f"https://youtu.be/{video_id}", "privacyStatus": meta["privacyStatus"]}
    save_state(slug, state)

    result = dict(state["youtube"])
    if meta.get("thumbnail"):
        try:
            yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(base / meta["thumbnail"]))).execute()
            result["thumbnail"] = "set"
        except HttpError as exc:
            result["thumbnail"] = f"failed (channel may need phone verification): {exc.reason}"
    if (base / "render/subs.srt").exists() and meta.get("uploadCaptions", False):
        cap = {"snippet": {"videoId": video_id, "language": lang, "name": ""}}
        yt.captions().insert(part="snippet", body=cap, media_body=MediaFileUpload(str(base / "render/subs.srt"))).execute()
        result["captions"] = "uploaded"

    from .analytics import register_video
    register_video(slug, video_id, meta)
    return result


def update_metadata(slug: str, title: str = "", description: str = "", tags: list[str] | None = None) -> dict:
    """Change title/description/tags of an uploaded video, e.g. for a manual A/B swap. Costs 50 units."""
    vid = load_state(slug)["youtube"]["video_id"]
    yt = youtube()
    current = yt.videos().list(part="snippet", id=vid).execute()["items"][0]["snippet"]
    snippet = {k: current[k] for k in ("title", "description", "categoryId") if k in current}
    snippet["tags"] = current.get("tags", [])
    if title:
        snippet["title"] = title
    if description:
        snippet["description"] = description
    if tags is not None:
        snippet["tags"] = tags
    yt.videos().update(part="snippet", body={"id": vid, "snippet": snippet}).execute()
    from .analytics import log_change
    log_change(vid, {k: v for k, v in {"title": title, "description": bool(description), "tags": tags}.items() if v})
    return {"video_id": vid, "title": snippet["title"]}
