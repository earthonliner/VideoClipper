---
name: assets
description: 素材与配乐——为每个镜头检索、下载可商用素材并选择背景音乐。script 批准后使用。
---

# 素材与配乐

## 画面
对每个 `visual.file` 为空且有 `query` 的 scene：
1. `stock_search(query, kind="video")`，先查 Pexels，结果不理想再查 Pixabay；`kind="image"` 作为补充。
2. 挑选标准：横屏、宽度 ≥1920、时长 ≥ 镜头时长（短了会循环播放）、内容和旁白直接相关、同一视频内色调统一。
3. `stock_download(slug, scene_id, item)`，把返回的 `file` 写进该 scene 的 `visual.file`，`type` 改为 `video` 或 `image`。
4. 用户自己提供的素材，或本地 ComfyUI / Draw Things 生成的图片，放进 `assets/` 后调 `asset_register` 记录来源和授权。
5. 实在找不到合适的素材时，用 `color` 加 `overlay_text`，并告诉用户。

## 配乐
1. `music_scan` 收录 `music/` 下新放进来的曲子；对还没打标签的曲子，根据文件名和来源用 `music_tag` 补上情绪标签。
2. `music_list(mood)` 选一首和视频情绪匹配、时长接近视频长度的曲子，写进 `storyboard.bgm.file`，`volume` 建议 0.10–0.18（渲染时会在人声出现时自动压低背景音乐）。
3. 曲库为空时，提醒用户去 YouTube Studio 的“音频库”或 Pixabay Music 下载几首放进 `music/`。
