---
name: publish
description: 发布包与上传——生成标题、描述、标签、缩略图，审核后上传 YouTube。final_cut 批准后使用。
---

# 发布包与上传

## 标题
- 写 5 个候选，放进 `title_alternatives`，选最好的一个作为 `title`。
- 长度控制在 60 个字符以内（移动端不会被截断），把核心关键词放在前面。
- 制造好奇心，但不能标题党：标题的承诺必须在视频里兑现。参考 playbook 里验证过有效的标题句式。

## 描述
- 前两行是摘要和关键词，搜索结果和折叠前都只显示这部分。
- 章节时间戳：用 `audio/*.mp3` 的时长累加计算，第一个必须是 `0:00`。
- 素材致谢：Pexels / Pixabay 不强制署名，但列出来更稳妥；从 `licenses.json` 生成。
- 结尾加 2–3 个话题标签（#xxx）。

## 标签
- 10–15 个：核心词、长尾词、中英文同义词，总长度不超过 500 字符。

## 缩略图
1. `frame_extract` 截取 2–3 个高光帧，或者用素材图。
2. `thumbnail_make` 至少做 a 和 b 两版：3–6 个字的大字，用 `[ ]` 高亮关键词；文字和标题互补，不要重复标题。
3. 用户选定后，把文件名写进 `publish.json.thumbnail`。

## features
把 `features` 填完整（topic_type、hook_type、length_bucket、thumb_style、title_pattern）。复盘时要用这些字段做归因分析。

## 上传
1. `publish_validate` 必须返回空列表。
2. 把标题、缩略图和隐私设置汇总给用户确认，用户通过后调 `approve(slug, "publish")`。
3. `youtube_upload(slug)`，然后把视频链接告诉用户。默认设为 private，提醒用户在 Studio 里检查后再公开，或者使用 `publishAt` 定时发布。
4. 如果缩略图设置失败，说明频道还没完成手机验证，请用户去 youtube.com/verify 完成验证。
