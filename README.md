# multi-platform-publisher

> 一句话写文章，AI 自动搜资料、写稿、配图、推送到草稿箱。微信公众号、小红书、今日头条三平台全覆盖。

基于 WorkBuddy AI 助手的多平台内容自动化 Skill 套件。从选题到发布，平均 15 分钟出稿，告别手动排版、IP 白名单地狱和反爬检测。

## 包含的 Skill

| Skill | 平台 | 版本 | 核心能力 |
|-------|------|------|----------|
| [wechat-publisher](./SKILL.md) | 微信公众号 | v2.0.0 | 云托管免鉴权推送草稿箱、PIL 自动配图 |
| [xhs-auto-publisher](./xhs-auto-publisher/SKILL.md) | 小红书 | v1.0 | 持久化登录、图文笔记发布、话题标签 |
| [toutiao-auto-publisher](./toutiao-auto-publisher/SKILL.md) | 今日头条 | v1.5.1 | playwright-stealth 反检测、正文配图穿插插入、草稿模式 |

## 工作流

```
用户一句话选题
    ↓
WebSearch 多角度搜索最新资讯
    ↓
AI 撰写文章（各平台差异化字数/风格）
    ↓
PIL 自动生成封面 + 正文配图（无 AI 水印）
    ↓
推送至对应平台草稿箱 / 直接发布
```

## 各平台特性

### 微信公众号（咸鱼观天下）

- **免鉴权推送**：微信云托管 + 开放接口服务，彻底告别 IP 白名单频繁变动
- **字节数校验**：标题 <=30 字节、摘要 <=64 字节，推送前自动检查不翻车
- **Markdown 转换**：自动将 Markdown 转为微信公众号兼容的 HTML，支持配图占位符
- **全自动配图**：PIL 生成暗色科技风信息图，封面 900x383（2.35:1）
- **可自定义文风**：默认通俗科普风格，可在 SKILL.md 中调整为任意风格

### 小红书

- **持久化登录**：`launch_persistent_context` + 扫码一次，Cookie 自动保存
- **图文笔记发布**：标题、正文、多图上传、话题标签一站式搞定
- **iframe 表单处理**：整个发布表单在 iframe 内，所有操作在 frame 上执行
- **逐张上传**：file input 不支持多文件同时传，自动逐张上传

### 今日头条

- **playwright-stealth 反检测**：隐藏 Playwright 自动化特征，绕过头条 7050 封锁
- **正文配图穿插插入**：spice API 批量上传拿 CDN URL + `execCommand('insertHTML')` 就地插入，图片不再堆文末
- **标题防丢字**：delay=120ms 键盘输入 + 长度校验 + JS 补全
- **封面兜底策略**：封面上传失败不阻断，头条自动用正文第一张配图当封面
- **ProseMirror 编辑器**：`keyboard.type(delay=30)` 逐行输入触发自动保存

## 效果数据

| 指标 | 手动 | 使用本套件 |
|------|------|------------|
| 选题+搜资料 | 30-60 分钟 | 2 分钟（自动搜索） |
| 写稿 | 60-120 分钟 | 3 分钟（AI 生成） |
| 配图 | 30-60 分钟 | 2 分钟（PIL 自动生成） |
| 排版+推送 | 20-30 分钟 | 1 分钟（一条命令） |
| **总计** | **2-4 小时** | **约 15 分钟** |

## 快速开始

### 前置条件

- [WorkBuddy](https://workbuddy.com) 桌面客户端
- 各平台账号（微信公众号需服务号或已认证订阅号、小红书、今日头条）
- Python 3.10+（配图生成用）
- 微信云托管服务（仅公众号推送需要，配置见 [SETUP.md](./SETUP.md)）

### 安装

1. 下载本仓库：

```bash
git clone https://github.com/xiaohao80/wechat-article-publisher.git
```

2. 将对应的 skill 目录复制到 WorkBuddy 技能目录：

```bash
# 公众号（根目录即 skill）
cp SKILL.md scripts/ ~/.workbuddy/skills/wechat-publisher/

# 小红书
cp -r xhs-auto-publisher/ ~/.workbuddy/skills/

# 今日头条
cp -r toutiao-auto-publisher/ ~/.workbuddy/skills/
```

3. 公众号需按照 [SETUP.md](./SETUP.md) 完成云托管配置（一次性，约 20 分钟）

4. 小红书/头条首次使用需扫码登录（扫码后 Cookie 自动持久化，有效期约 30 天）

5. 在 WorkBuddy 对话中说：

> 写一篇关于 XXX 的公众号文章，写完推送到草稿箱
>
> 发一篇小红书笔记，主题是 XXX
>
> 发头条，主题是 XXX

对应 Skill 会自动加载，完整流程一条龙。

## 目录结构

```
wechat-article-publisher/
├── README.md                          # 本文件
├── SETUP.md                           # 公众号云托管配置指南
├── LICENSE                            # MIT 协议
├── SKILL.md                           # 公众号 Skill 主文件
├── scripts/                           # 公众号脚本
│   ├── publish_client.py              # 推送客户端（Python）
│   ├── server.js                      # 云托管服务端（Node.js/Express）
│   ├── Dockerfile                     # Docker 构建文件
│   ├── package.json                   # Node 依赖声明
│   └── gen_charts_template.py         # PIL 配图生成模板
├── xhs-auto-publisher/                # 小红书 Skill
│   ├── SKILL.md
│   └── xhs_publisher.py
└── toutiao-auto-publisher/            # 今日头条 Skill
    ├── SKILL.md
    └── toutiao_publisher.py
```

## 技术架构

```
WorkBuddy AI（本地）
    │
    ├── WebSearch → 搜索最新资讯
    ├── AI 写稿 → 生成 Markdown 文章
    ├── PIL → 生成封面 + 正文配图
    │
    ├── 微信公众号：publish_client.py → 微信云托管 → 草稿箱
    ├── 小红书：xhs_publisher.py（Playwright）→ 直接发布
    └── 今日头条：toutiao_publisher.py（Playwright + stealth）→ 草稿箱/发布
```

## 常见问题

<details>
<summary>公众号推送报 40164（IP 不在白名单）</summary>

说明云调用的「开放接口服务」没开启。去云托管控制台 -> 云调用 -> 开放接口服务 -> 开启开关 -> 配置接口 -> 勾选接口 -> 保存。详见 SETUP.md。
</details>

<details>
<summary>公众号推送报 45003 / 45004</summary>

标题超过 30 字节或摘要超过 64 字节。注意中文 UTF-8 编码下每个字占 3 字节，10 个中文 = 30 字节。
</details>

<details>
<summary>头条发布报 7050 保存失败</summary>

Playwright 被头条反爬检测到了。确认安装了 `playwright-stealth` 并在代码中调用了 `Stealth().apply_stealth_async(context)`。
</details>

<details>
<summary>头条正文配图全堆在文末</summary>

使用 v1.5.0+ 版本，配图用 `[配图N]` 占位符标记位置，脚本会通过 spice API + `execCommand('insertHTML')` 在占位符位置就地插入。
</details>

<details>
<summary>小红书/头条提示需要重新扫码</summary>

Cookie 过期了（约 30 天有效期）。重新执行 `login` 命令扫码即可。
</details>

<details>
<summary>配图字体报错</summary>

Windows 用微软雅黑，Mac 用 PingFang SC，Linux 需要安装 Noto Sans CJK。模板脚本会自动检测系统。
</details>

## 实战文章

使用本套件已成功发布的内容：

**微信公众号「咸鱼观天下」**
1. AI 删库跑路实录
2. 马斯克砸 600 亿买 Cursor
3. 35 岁遇上 AI，慌不慌
4. 用网接火箭有多野
5. AI 替我发公众号（本工具的自我介绍）

**今日头条**
1. LV 赢了 1030 万官司，结果全网叫它厕所包
2. Mira Murati 的 Thinking Machines Lab 发布 Inkling

## 作者

**摸鱼哥**（微信公众号：咸鱼观天下）

- **微信公众号**：咸鱼观天下（程序员视角的科技吐槽，有温度有态度）
- **GitHub**：[@xiaohao80](https://github.com/xiaohao80) — Star ⭐ 一下，下次更新不迷路
- **小红书**：搜「咸鱼观天下」，踩坑实录和技术分享都在这

如果这个 Skill 帮到了你，来这些平台打个招呼就行。

## 协议

[MIT](./LICENSE) - 随便用，改了记得署名。
