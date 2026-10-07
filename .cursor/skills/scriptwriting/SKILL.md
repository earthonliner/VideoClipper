---
name: scriptwriting
description: 剧本与分镜——把已批准的选题写成口播剧本，并拆成 storyboard.json 镜头。topic 批准后使用。
---

# 剧本与分镜

## 剧本（script.md）
- 钩子：前 5–15 秒抛出问题、反常识结论或结果预告，不要寒暄。
- 结构：承诺 → 3–5 个段落（每段一个要点，用一个具体例子或数据支撑）→ 总结 → CTA（订阅或看下一个视频）。
- 口语化：短句为主，每句尽量不超过 25 个字，避免书面连接词。
- 语速参考：中文约 4–4.5 字/秒（edge-tts `+0%`），据此估算时长。

## 分镜（storyboard.json）
- 一个 scene 放 1–3 句旁白，时长约 3–8 秒，保证画面经常切换。
- `visual.type`：
  - `video`：素材视频，`file` 为项目内相对路径，可设 `start` 秒数跳过片头。
  - `image`：图片，自动做 Ken Burns 缓慢推近，`zoom` 默认 1.12。
  - `color`：纯色底，配合 `overlay_text` 做标题卡或章节卡。
- 先在 `visual.query` 写英文检索词（素材阶段使用），`file` 留空。
- `overlay_text`：画面中央的大字，只在强调关键数字或章节时使用。
- 无旁白的镜头设置 `duration`（秒）。
- 声音：用 `voice_list("zh-")` 挑音色，常用 `zh-CN-YunxiNeural`（男，叙事）、`zh-CN-XiaoxiaoNeural`（女，温和）。英文频道用 `en-US-AndrewMultilingualNeural` 等。

完成后请用户审核剧本和分镜，用户通过后调 `approve(slug, "script")`。
