---
name: analyze
description: 数据复盘与自我迭代——拉取 YouTube 数据，分析单个视频或频道整体，提出 playbook 更新。用户要求复盘或分析时使用。
---

# 复盘与自我迭代

## 拉数据
- `analytics_sync()`。数据有 2–3 天延迟；发布后第 3、7、28 天各复盘一次。
- API 不提供展示次数和点击率（CTR）。需要这两项时，请用户从 YouTube Studio 的“分析 → 覆盖面”截图或导出 CSV，放进项目目录。

## 单视频复盘（写进 `projects/<slug>/report.md`）
`analytics_report(slug=...)`，重点看：
- **钩子**：`retention_at[0.05]` 与频道其他视频比较；低于 0.7 说明开头没抓住人。
- **流失点**：`biggest_drops` 对照 `audio/*.mp3` 的时长累加，定位到具体镜头和旁白，分析原因（节奏拖沓、画面重复、跑题）。
- **流量来源**：搜索占比高说明标题和关键词起作用；浏览和推荐占比高说明缩略图和留存起作用。
- 和 `channel_medians` 对比，给出 3 条具体可执行的改进。

## 频道级分析
`analytics_overview()` 按 `features` 分组比较 views_per_day、avg_view_pct 和 subs_gained，找出哪些特征和高表现相关。样本少于 5 个时，结论要标注“待验证”。

## 更新知识库
1. 把发现写进 `knowledge/learnings.md`（追加，带日期和证据：哪几个视频、哪些数据）。
2. 当某条规律有 ≥3 个视频支持时，提议修改 `knowledge/playbook.md`，并给出 diff。**用户确认后才写入。**
3. 想做标题 A/B 测试时：征得用户同意后用 `youtube_update_metadata` 更换标题，系统会自动记录变更时间；7 天后对比前后的 views_per_day。
