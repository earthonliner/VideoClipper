"""MCP server exposing the video pipeline to the Cursor agent (stdio transport)."""
from mcp.server.mcpserver import MCPServer

from . import analytics, assets, doctor, project, render, thumbnail, voice, youtube

server = MCPServer(
    "video-studio",
    instructions=(
        "Tools for producing YouTube videos. Follow .cursor/rules/video-pipeline.mdc. "
        "Never call approve unless the user explicitly approved in this conversation."
    ),
)


@server.tool()
def env_check() -> dict:
    """Check ffmpeg, fonts, API keys and YouTube auth. Run before starting a project."""
    return doctor.run()


@server.tool()
def project_create(topic: str) -> dict:
    """Create a new project folder (brief/script/storyboard/publish templates) and return its slug."""
    return project.create_project(topic)


@server.tool()
def project_list() -> list[dict]:
    """List all projects with their approved gates."""
    return project.list_projects()


@server.tool()
def project_status(slug: str) -> dict:
    """Show gate approvals (invalidated if files changed since), file counts and YouTube state."""
    return project.status(slug)


@server.tool()
def approve(slug: str, gate: str, note: str = "") -> dict:
    """Record the USER's approval of a gate: topic | script | final_cut | publish.

    Only call this when the user has explicitly said they approve in the chat. The approval
    fingerprints the gate's files, so any later edit voids it and requires re-approval.
    """
    return project.approve(slug, gate, note)


@server.tool()
def youtube_search(query: str, max_results: int = 10, order: str = "relevance", region: str = "",
                   language: str = "", published_after_days: int = 0) -> list[dict]:
    """Search YouTube videos with view/like stats for topic research. order: relevance|viewCount|date|rating.
    Costs ~101 of the 10,000 daily quota units; use sparingly."""
    return youtube.search_videos(query, max_results, order, region, language, published_after_days)


@server.tool()
def stock_search(query: str, kind: str = "video", provider: str = "pexels", per_page: int = 8,
                 orientation: str = "landscape") -> list[dict]:
    """Search free commercial-use stock footage/photos. kind: video|image, provider: pexels|pixabay.
    Queries work best in English."""
    return assets.search_stock(query, kind, provider, per_page, orientation)


@server.tool()
def stock_download(slug: str, scene_id: str, item: dict) -> dict:
    """Download one item returned by stock_search into the project and record its license.
    Returns the relative file path to put in storyboard visual.file."""
    return assets.download_asset(slug, scene_id, item)


@server.tool()
def asset_register(slug: str, scene_id: str, file: str, source: str, license: str) -> dict:
    """Record provenance for a locally generated or user-supplied asset already in the project folder."""
    return assets.register_local_asset(slug, scene_id, file, source, license)


@server.tool()
def music_scan() -> dict:
    """Index new audio files dropped into music/ and list tracks still missing mood tags."""
    return assets.scan_music()


@server.tool()
def music_tag(file: str, moods: list[str], source: str = "", license: str = "") -> dict:
    """Set mood tags (e.g. calm, epic, upbeat, suspense, tech) and license info for a library track."""
    return assets.tag_music(file, moods, source, license)


@server.tool()
def music_list(mood: str = "") -> list[dict]:
    """List music library tracks, optionally filtered by mood. Use the 'file' value as storyboard bgm.file."""
    return assets.list_music(mood)


@server.tool()
def voice_list(locale_prefix: str = "zh-") -> list[dict]:
    """List free Edge TTS voices for a locale prefix (zh-, en-US, ja-...)."""
    return voice.list_voices(locale_prefix)


@server.tool()
def tts_generate(slug: str, force: bool = False) -> list[dict]:
    """Generate narration mp3 + sentence-timed subtitles for every storyboard scene (cached by text)."""
    return voice.generate_voiceover(slug, force)


@server.tool()
def render_video(slug: str) -> dict:
    """Render render/final.mp4 from storyboard.json: scene clips, burned subtitles, ducked BGM, -14 LUFS."""
    return render.render(slug)


@server.tool()
def frame_extract(slug: str, at_seconds: float, out_name: str = "frame.jpg") -> str:
    """Grab a still from the final cut into thumbs/ to use as a thumbnail background."""
    return str(render.extract_frame(slug, at_seconds, out_name))


@server.tool()
def thumbnail_make(slug: str, source: str, text: str, variant: str = "a", accent: str = "#FFD400",
                   position: str = "left") -> dict:
    """Create thumbs/thumb-<variant>.jpg (1280x720, <2MB). source is a project-relative image path.
    Wrap words in [brackets] to highlight them in the accent color."""
    return thumbnail.make_thumbnail(slug, source, text, variant, accent, position)


@server.tool()
def publish_validate(slug: str) -> list[str]:
    """Validate publish.json against YouTube limits. Empty list means OK."""
    return youtube.validate_publish(slug)


@server.tool()
def youtube_upload(slug: str) -> dict:
    """Upload the final cut with publish.json metadata and thumbnail. Refuses unless the user approved
    both final_cut and publish and the files are unchanged since. Costs ~1,650 quota units."""
    return youtube.upload(slug)


@server.tool()
def youtube_update_metadata(slug: str, title: str = "", description: str = "", tags: list[str] | None = None) -> dict:
    """Change title/description/tags of an uploaded video (A/B iteration). Ask the user first."""
    return youtube.update_metadata(slug, title, description, tags)


@server.tool()
def analytics_sync(limit: int = 200) -> dict:
    """Pull lifetime metrics for recent uploads into the local SQLite database."""
    return analytics.sync(limit)


@server.tool()
def analytics_overview() -> dict:
    """All videos with features + latest metrics and channel medians, sorted by views/day."""
    return analytics.overview()


@server.tool()
def analytics_report(video_id: str = "", slug: str = "") -> dict:
    """Deep dive for one video: metric history, retention checkpoints, biggest drop-offs, traffic sources."""
    return analytics.report(video_id, slug)


@server.tool()
def analytics_set_features(video_id: str, features: dict) -> str:
    """Tag a video with content features (topic_type, hook_type, length_bucket, thumb_style, ...) for analysis."""
    analytics.set_features(video_id, features)
    return "ok"


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
