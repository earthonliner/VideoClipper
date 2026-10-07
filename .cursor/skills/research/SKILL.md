---
name: research
description: 选题研究——根据用户描述找到有需求、有差异化的选题，产出 brief.md。用户提出新视频想法时使用。
---

# 选题研究

1. `env_check`；`project_create(topic)` 得到 slug。
2. 读 `knowledge/playbook.md` 和 `knowledge/learnings.md`；如果 `data/studio.db` 有数据，调 `analytics_overview` 看哪些特征的视频表现好。
3. 调研：
   - 用网页搜索看话题热度、近期新闻、Reddit / 知乎 / B 站上的讨论。
   - `youtube_search(query, order="viewCount", published_after_days=365)`，中文和英文关键词各查 1–2 次。重点看：播放量与频道体量的比例（小频道的高播放量 = 需求强）、标题句式、时长。
   - 记下排名前列视频没有覆盖的角度（差异化机会）。
4. 写 `brief.md`：3–5 个候选选题，每个附证据（链接 + 播放数据）和风险，最后给出推荐。
5. 向用户简要列出候选，请用户选择。用户确认后，把选择写进 brief 的“用户选定”部分，再调 `approve(slug, "topic")`。
