---
name: xhs-auto-publisher
description: 小红书自动发布工具 — 基于 Playwright
  的浏览器自动化，持久化登录，支持图文笔记发布和搜索。当用户需要发布小红书笔记、搜索小红书内容、检查小红书登录状态时使用此 skill。
version: 1.0.1
author: 摸鱼哥（咸鱼观天下）
homepage: https://github.com/xiaohao80/wechat-article-publisher
disable: true
---

# 小红书自动发布工具

基于 Playwright 的浏览器自动化脚本，持久化登录态，支持图文笔记发布和搜索。

## 触发场景

- 用户要求发布小红书笔记
- 用户要求搜索小红书内容
- 用户要求检查小红书登录状态
- 用户提到"发小红书"、"小红书发布"、"小红书搜索"等关键词

## 前置条件

### 1. Python 环境

脚本依赖 Playwright，需要安装在 Python venv 中：

```bash
# Python 路径（优先用 managed 版本）
PYTHON="C:\Users\{用户名}\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
# 或系统 Python（需已安装 playwright）
PYTHON="C:\Program Files\Python311\python.exe"
```

### 2. 安装 Playwright + Chromium（首次使用）

```bash
# 安装 playwright 包
"$PYTHON" -m pip install playwright

# 安装 Chromium 浏览器（国内必须用镜像，否则下载卡死）
# Windows PowerShell:
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://cdn.npmmirror.com/binaries/playwright"
"$PYTHON" -m playwright install chromium

# Linux/macOS:
PLAYWRIGHT_DOWNLOAD_HOST="https://cdn.npmmirror.com/binaries/playwright" "$PYTHON" -m playwright install chromium
```

### 3. 首次登录（扫码）

```bash
"$PYTHON" "{SKILL_DIR}/xhs_publisher.py" login
```

会弹出浏览器窗口，用手机小红书 APP 扫码登录。登录态保存在 `~/.xhs-browser-data/`，**后续无需重复登录**。

## 使用方法

### 检查登录状态

```bash
"$PYTHON" "{SKILL_DIR}/xhs_publisher.py" check
```

### 发布图文笔记（直接发布）

```bash
"$PYTHON" "{SKILL_DIR}/xhs_publisher.py" publish \
  --title "标题（最多20字）" \
  --content "正文内容" \
  --images "图1.png" "图2.png" "图3.png" \
  --topics "话题1" "话题2" "话题3"
```

### 从文件读取正文（推荐，避免命令行转义问题）

```bash
"$PYTHON" "{SKILL_DIR}/xhs_publisher.py" publish \
  --title "标题" \
  --content-file "正文.md" \
  --images "图1.png" "图2.png" \
  --topics "话题1" "话题2"
```

### 搜索笔记

```bash
"$PYTHON" "{SKILL_DIR}/xhs_publisher.py" search "搜索关键词" --limit 10
```

### 指定调试截图目录

```bash
"$PYTHON" "{SKILL_DIR}/xhs_publisher.py" publish --title "标题" --content "正文" --images img.png --debug-dir "/tmp/xhs-debug"
```

## 参数说明

### publish 命令

| 参数 | 必填 | 说明 |
|---|---|---|
| `--title` | 是 | 笔记标题，最多20字 |
| `--content` | 否 | 笔记正文（与 `--content-file` 二选一） |
| `--content-file` | 否 | 从文件读取正文（推荐，避免转义问题） |
| `--images` | 是 | 图片路径，可多张（空格分隔） |
| `--topics` | 否 | 话题标签，可多个 |
| `--draft` | 否 | 存草稿箱（实验性，可能不可靠） |
| `--debug-dir` | 否 | 调试截图保存目录（默认当前目录） |

## ⚠️ 已知限制

### 1. 草稿模式不可靠
`--draft` 参数点击"暂存离开"按钮，但该按钮是 Vue 自定义组件 `<xhs-publish-btn>` 内部的元素，点击可能穿透不到内部 button。**建议直接发布，不要用草稿模式**。

### 2. 标题字数限制
小红书标题最多20个中文字符，超过会被截断或发布失败。

### 3. 图片格式
- 支持 JPG/PNG
- 建议 3:4 竖版（1080×1440）
- 最多 18 张图
- file input 不支持多文件同时传入，脚本已自动逐张上传

### 4. 发布即公开
小红书发布后**直接公开可见**，不存在"仅自己可见"的中间状态。如需审核后再公开，请先在本地确认文案和配图无误。

### 5. 浏览器窗口
脚本以 `headless=False` 运行，会弹出浏览器窗口。发布过程中不要手动操作浏览器窗口。

## 技术架构

### 发布流程（9步）

1. 检查登录状态
2. 访问 `https://creator.xiaohongshu.com/publish/publish`
3. **找到 iframe**（整个发布表单都在 iframe 里，不在主页面 DOM 中）
4. 在 iframe 内切换到"上传图文" tab
5. 逐张上传图片（file input 不支持多文件）
6. 输入标题
7. 输入正文 + 话题标签
8. 点击发布按钮
9. 检查发布结果

### 关键技术踩坑点（必读）

1. **整个表单在 iframe 里**：所有操作（tab切换、图片上传、标题/正文输入、按钮点击）都必须在 `frame` 对象上执行，不能在 `self.page` 上执行。

2. **发布按钮是 Vue 自定义组件**：`<xhs-publish-btn>` 是 Web Component，内部按钮不在 light DOM 里。需要用 `frame.locator('xhs-publish-btn').click(position={x: 像素, y: 像素})` 点击。

3. **position 是像素偏移量不是比例**：`position={'x': 0.78, 'y': 0.5}` 会在左上角(0.78px, 0.5px)点击，完全无效。必须算出实际像素值：`position={'x': int(rect_w * 0.65), 'y': int(rect_h * 0.5)}`。

4. **"发布"按钮在容器右侧约65%位置**，"暂存离开"在左侧约25%位置。容器通常 680×90 像素。

5. **elementFromPoint 无效**：`document.elementFromPoint(x, y)` 返回的是 Vue 组件外壳 `<xhs-publish-btn>`，`.click()` 不会触发内部 button 的事件。

6. **Playwright 镜像下载**：Chromium 官方 CDN 被墙，必须设 `PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright`。

7. **持久化登录**：用 `launch_persistent_context` + `userDataDir=~/.xhs-browser-data`，扫码一次后 cookie 自动保存，后续无需重新扫码。

## 脚本路径

```
{SKILL_DIR}/xhs_publisher.py
```

`{SKILL_DIR}` 为本 skill 所在目录，通常为 `~/.workbuddy/skills/xhs-auto-publisher/`。

## 关于作者

本 Skill 由 **摸鱼哥** 原创开发，3小时死磕 Vue 自定义组件点击穿透问题才跑通发布流程。

如果你觉得有用，欢迎来这些地方找我玩：

- **微信公众号**：咸鱼观天下（程序员视角的科技吐槽，有温度有态度）
- **GitHub**：[@xiaohao80](https://github.com/xiaohao80) — Star ⭐ 一下，下次更新不迷路
- **小红书**：搜「咸鱼观天下」，踩坑实录和技术分享都在这

这个脚本能帮你省掉手动发笔记的重复劳动，但文案和配图还是得你自己用心。工具是工具，内容是内容。
