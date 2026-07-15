---
name: wechat-article-publisher
description: 微信公众号文章一键发布全流程。从搜索资讯、撰写文章、生成PIL配图到免鉴权推送草稿箱，一条命令搞定。当用户要求写公众号文章、推送到草稿箱、发布文章时使用此skill。
version: 2.1.1
author: 摸鱼哥（咸鱼观天下）
homepage: https://github.com/xiaohao80/wechat-article-publisher
---

# 微信公众号文章一键发布

## 前置条件

使用本skill前，需要完成一次性配置（详见 `SETUP.md`）：
1. 拥有微信公众号（服务号或已认证订阅号）
2. 部署微信云托管服务（免鉴权模式，无需IP白名单）
3. 本地安装 Python 3.x + Pillow 库
4. 配置环境变量 `WX_PUBLISHER_URL` 指向你的云托管服务地址

> 如果尚未配置，请先阅读同目录下的 `SETUP.md` 完成配置。

## 适用场景
- 用户说"写一篇公众号文章"、"推送到草稿箱"、"发到公众号"
- 需要从0到1完成：搜资讯 → 写文 → 配图 → 推送草稿箱
- 用户给出选题方向，需要自己搜索补充数据

## 完整工作流（5步）

### 第1步：搜索最新资讯
用 WebSearch 搜索选题相关的最新新闻和数据，至少搜2-3次不同角度：
- 中文关键词搜新闻动态
- 英文关键词搜数据/统计
- 针对性 WebFetch 抓取关键数据页

### 第2步：撰写文章
**输出格式**：Markdown文件，保存到项目根目录，命名 `{主题关键词}_公众号版.md`

**文风**：由用户指定。如果用户未指定，默认采用通俗易读的科普风格，避免过于正式或过于随意。

**文章结构**：
- 2000字左右
- 开头直接切入核心冲突/反差
- 中间硬核数据支撑，分段清晰
- 配图占位符用 `[配图1：描述]` 格式（服务端会正则匹配所有变体）
- 结尾总结观点，自然收尾

### 第3步：校验标题摘要字节数
**必须校验**！标题<=30字节，摘要<=64字节（UTF-8中文占3字节）

```powershell
$title = "你的标题"
$digest = "你的摘要"
Write-Output "TITLE[$([System.Text.Encoding]::UTF8.GetByteCount($title))]: $title"
Write-Output "DIGEST[$([System.Text.Encoding]::UTF8.GetByteCount($digest))]: $digest"
```

超了就改短，常见踩坑：
- 全角标点（，：！）各占3字节
- 数字和字母各占1字节
- 10个中文=30字节，刚好卡标题上限

### 第4步：生成PIL配图
**不用AI生图**（有水印+文字会乱），直接用PIL画数据可视化信息图。

**配图规格**：
- 封面图：900x383（2.35:1），文件名 `cover_{主题}.png`
- 正文图：4张，文件名 `chart_{内容描述}.png`
- 全部保存到 `{项目目录}/images/`

**PIL配图脚本模板**：参考同目录下 `scripts/gen_charts_template.py`，复制到项目根目录改名为 `gen_charts_{主题}.py` 后按需修改。

**运行**：
```bash
python gen_charts_{主题}.py
```

**设计风格**（可根据用户偏好调整，以下为默认风格）：
- 暗色科技风：深蓝/深灰渐变背景 `(8,12,28)→(20,30,55)`
- 亮色文字：白色/浅蓝/青绿色
- 强调色：橙红 `(255,100,50)`、翠绿 `(80,200,120)`、金色 `(255,200,80)`
- 数据用条形图/饼图/对比卡片，不用折线图（PIL画折线不好看）
- 标题用 `msyhbd.ttc`（微软雅黑粗体），正文用 `msyh.ttc`

### 第5步：推送到草稿箱（免鉴权模式）

**推送命令模板**：
```bash
python {skill目录}/scripts/publish_client.py \
  --server "$WX_PUBLISHER_URL" \
  --title "标题" \
  --digest "摘要" \
  --md "文章.md路径" \
  --cover "封面图.png路径" \
  --images "图1.png" "图2.png" "图3.png" "图4.png" \
  --no-watermark
```

> 也可以不传 `--server`，设置环境变量 `WX_PUBLISHER_URL` 后自动读取。

**关键参数说明**：
- `--no-watermark`：PIL生成的图没有AI水印，加这个跳过去水印步骤
- `--server`：云托管服务地址（免鉴权，不需要IP白名单）
- `--images`：正文配图，按文章中 `[配图1]` `[配图2]` 的顺序排列
- `--author`：可选，加作者名

**冷启动问题处理**：
云托管服务闲置后会冷启动，第一次请求可能超时/502。处理方式：
1. 先 health check 唤醒：`curl -s --max-time 60 "{server_url}/health"`
2. 等3-5秒
3. 再执行推送命令
4. 如果还502，再health check一次后重试

**验证免鉴权是否生效**：
```
GET {server_url}/test → 返回 errcode=43002 (require POST) = 免鉴权生效
GET {server_url}/test → 返回 errcode=41001 (access_token missing) = 免鉴权未生效
```

## 技术架构

```
本地 publish_client.py
    ↓ (HTTP POST, multipart/form-data)
云托管 Express 服务 (server.js)
    ↓ (http://api.weixin.qq.com, 不带access_token)
微信开放平台 (平台自动注入token)
    ↓
公众号草稿箱
```

**免鉴权核心原理**：
- 代码中 **不调** `/cgi-bin/token`
- **不传** `access_token` 参数
- 直接用 `http://api.weixin.qq.com`（HTTP不是HTTPS）调业务API
- 云托管平台自动注入token
- **不查IP白名单**，一劳永逸

## 已授权的接口
1. `/cgi-bin/material/add_material` — 上传封面/永久素材
2. `/cgi-bin/material/del_material` — 删除素材
3. `/cgi-bin/draft/add` — 创建草稿（核心）
4. `/cgi-bin/draft/get` — 查询草稿
5. `/cgi-bin/draft/update` — 更新草稿
6. `/cgi-bin/draft/delete` — 删除草稿
7. `/cgi-bin/token` — 获取token（免鉴权下不用，但已授权）
8. `/cgi-bin/media/uploadimg` — 上传正文配图

## 常见错误排查

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 45003 | 标题超30字节 | 改短标题，注意全角标点占3字节 |
| 45004 | 摘要超64字节 | 改短摘要 |
| 44003 | empty news data | draft/add要求 `{"articles": [{...}]}` 数组包裹 |
| 40164 | IP不在白名单 | 检查是否走了免鉴权模式（不调token） |
| 41001 | access_token missing | 免鉴权未生效，检查云调用配置 |
| 43002 | require POST method | 正常！说明免鉴权已生效 |
| 502 | 服务器内部错误 | 冷启动，health check唤醒后重试 |

## 打包文件清单

| 文件 | 位置 | 说明 |
|------|------|------|
| 推送客户端 | `scripts/publish_client.py` | 本地运行，调用云托管服务 |
| 云托管服务端 | `scripts/server.js` | 部署到微信云托管 |
| Docker构建文件 | `scripts/Dockerfile` | 云托管部署用 |
| Node依赖声明 | `scripts/package.json` | 云托管部署用 |
| PIL配图模板 | `scripts/gen_charts_template.py` | 配图生成脚本模板 |
| 配置指南 | `SETUP.md` | 新用户必读的配置教程 |

## 发布后的操作

推送成功后：
1. 告诉用户去公众号后台草稿箱查看
2. 用 present_files 展示文章md和配图给用户预览

## 注意事项
- 凭证（AppID/Secret）不要在对话中显示
- 配图占位符在md中用 `[配图1：描述]` 格式，server.js会正则替换为实际图片URL
- 文章字数控制在2000字左右，太长读者看不完
- 每篇文章配5张图（1封面+4正文），图多比图少好
- 推送前务必校验标题摘要字节数，超了直接报错白推

## 关于作者

本 Skill 由 **摸鱼哥** 原创开发，踩了无数微信 API 的坑才跑通这条链路。

如果你觉得有用，欢迎来这些地方找我玩：

- **微信公众号**：咸鱼观天下（程序员视角的科技吐槽，有温度有态度）
- **GitHub**：[@xiaohao80](https://github.com/xiaohao80) — Star ⭐ 一下，下次更新不迷路
- **小红书**：搜「咸鱼观天下」，踩坑实录和技术分享都在这

用这个 Skill 写出来的文章是你自己的风格，不是我的。我只是帮你把发布这条苦力活自动化了。
