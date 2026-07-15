# wechat-article-publisher

> 一句话写公众号文章，AI 自动搜资料、写稿、配图、推送到草稿箱。

基于 WorkBuddy AI 助手的微信公众号全流程自动化 Skill。从选题到草稿箱，平均 15 分钟出稿，告别手动排版和 IP 白名单地狱。

## 工作流

```
用户一句话选题
    ↓
WebSearch 多角度搜索最新资讯
    ↓
AI 撰写 2000 字文章（文风可自定义）
    ↓
PowerShell 校验标题/摘要字节数
    ↓
PIL 自动生成封面 + 4 张正文配图（无 AI 水印）
    ↓
云托管免鉴权推送到微信公众号草稿箱
```

## 核心特性

- **全自动配图**：PIL 生成暗色科技风信息图，封面 900x383（2.35:1），正文图自适应内容
- **免鉴权推送**：微信云托管 + 开放接口服务，彻底告别 IP 白名单频繁变动
- **字节数校验**：标题 <=30 字节、摘要 <=64 字节，推送前自动检查不翻车
- **Markdown 转换**：自动将 Markdown 转为微信公众号兼容的 HTML，支持配图占位符
- **可自定义文风**：默认通俗科普风格，可在 SKILL.md 中调整为任意风格

## 效果数据

| 指标 | 手动 | 使用本 Skill |
|------|------|--------------|
| 选题+搜资料 | 30-60 分钟 | 2 分钟（自动搜索） |
| 写稿 | 60-120 分钟 | 3 分钟（AI 生成） |
| 配图 | 30-60 分钟 | 2 分钟（PIL 自动生成） |
| 排版+推送 | 20-30 分钟 | 1 分钟（一条命令） |
| **总计** | **2-4 小时** | **约 15 分钟** |

## 快速开始

### 前置条件

- [WorkBuddy](https://workbuddy.com) 桌面客户端
- 已认证的微信公众号（服务号或已认证订阅号）
- Python 3.10+（配图生成用）
- 微信云托管服务（免鉴权推送用，配置见 [SETUP.md](./SETUP.md)）

### 安装

1. 下载本仓库的 zip 或 clone：

```bash
git clone https://github.com/你的用户名/wechat-article-publisher.git
```

2. 打开 WorkBuddy -> 导入技能 -> 拖入 zip 文件

3. 按照 [SETUP.md](./SETUP.md) 完成云托管配置（一次性，约 20 分钟）

4. 配置完成后，在 WorkBuddy 对话中说：

> 写一篇关于 XXX 的公众号文章，写完推送到草稿箱

Skill 会自动加载，完整流程一条龙。

## 目录结构

```
wechat-article-publisher/
├── SKILL.md                      # Skill 主文件（工作流文档）
├── SETUP.md                      # 新用户配置指南
├── LICENSE                       # MIT 协议
├── README.md                     # 本文件
└── scripts/
    ├── publish_client.py         # 推送客户端（Python）
    ├── server.js                 # 云托管服务端（Node.js/Express）
    ├── Dockerfile                # Docker 构建文件
    ├── package.json              # Node 依赖声明
    └── gen_charts_template.py    # PIL 配图生成模板
```

## 技术架构

```
WorkBuddy AI（本地）
    │
    ├── WebSearch → 搜索最新资讯
    ├── AI 写稿 → 生成 Markdown 文章
    ├── PIL → 生成封面 + 正文配图
    │
    └── publish_client.py（本地客户端）
            │
            ▼
    微信云托管（Express 服务）
            │
            ├── 去水印（sharp）
            ├── Markdown → HTML 转换
            ├── 上传封面（add_material）
            ├── 上传正文图（uploadimg）
            └── 创建草稿（draft/add）
                    │
                    ▼
            微信公众号草稿箱
```

**免鉴权原理**：云托管内不调用 `/cgi-bin/token`，不传 `access_token` 参数，直接用 `http://api.weixin.qq.com` 调业务 API，平台自动注入令牌。彻底绕过 IP 白名单。

## 常见问题

<details>
<summary>推送报 40164（IP 不在白名单）</summary>

说明云调用的「开放接口服务」没开启。去云托管控制台 -> 云调用 -> 开放接口服务 -> 开启开关 -> 配置接口 -> 勾选 8 个接口 -> 保存。详见 SETUP.md。
</details>

<details>
<summary>推送报 45003 / 45004</summary>

标题超过 30 字节或摘要超过 64 字节。注意中文 UTF-8 编码下每个字占 3 字节，10 个中文 = 30 字节。
</details>

<details>
<summary>推送报 502</summary>

云托管冷启动了，先调 `/health` 唤醒，等 5 秒再推。
</details>

<details>
<summary>配图字体报错</summary>

Windows 用微软雅黑，Mac 用 PingFang SC，Linux 需要安装 Noto Sans CJK。模板脚本会自动检测系统。
</details>

<details>
<summary>导入 WorkBuddy 报"名称重复"</summary>

这个 zip 是给别人用的。如果你本地已经有了同名 skill，不需要重复导入。
</details>

## 实战文章

使用本 Skill 已成功发布的文章：

1. AI 删库跑路实录
2. 马斯克砸 600 亿买 Cursor
3. 35 岁遇上 AI，慌不慌
4. 用网接火箭有多野
5. AI 替我发公众号（本工具的自我介绍）

## 作者

**摸鱼哥**（微信公众号：咸鱼观天下）

- **微信公众号**：咸鱼观天下（程序员视角的科技吐槽，有温度有态度）
- **GitHub**：[@xiaohao80](https://github.com/xiaohao80) — Star ⭐ 一下，下次更新不迷路
- **小红书**：搜「咸鱼观天下」，踩坑实录和技术分享都在这

如果这个 Skill 帮到了你，来这些平台打个招呼就行。

## 协议

[MIT](./LICENSE) - 随便用，改了记得署名。
