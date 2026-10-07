---
name: render
description: 配音与合成——生成 TTS 配音和字幕，渲染成片并交给用户审片。素材就绪后使用。
---

# 配音与合成

1. `tts_generate(slug)`：每个 scene 生成 `audio/<id>.mp3` 和句级字幕。旁白没变的 scene 会走缓存。
2. 用返回的时长检查总时长是否符合预期；偏差较大时调整 `voice_rate`（如 `+10%`），或删减旁白。
3. `render_video(slug)` 输出 `render/final.mp4`，包含：
   - 分镜按顺序硬切拼接，图片做缓慢推近；
   - 字幕烧录（`subtitles.burn`），同时生成 `render/subs.srt`；
   - 背景音乐在人声出现时自动压低，结尾淡出；整体响度归一到 -14 LUFS（YouTube 标准）。
4. 告诉用户成片路径和时长，请用户在 Finder 或 QuickTime 里打开 `projects/<slug>/render/final.mp4` 审片。
5. 根据用户的反馈修改 storyboard 或旁白，然后重新跑 tts 和 render。用户明确说“通过”后，调 `approve(slug, "final_cut")`。

常见问题：
- 字幕字体不对：在 `.env` 里设置 `SUBTITLE_FONT_NAME`，或在 storyboard 的 `subtitles.style` 里自定义 ASS 样式。
- 渲染慢：1080p 每分钟成片大约需要 1–2 分钟，属于正常范围。
