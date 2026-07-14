# 配置指南

本skill依赖微信云托管服务实现免鉴权推送。以下是完整的一次性配置步骤。

## 前置条件

- 已认证的微信公众号（服务号）
- 微信云托管账号（开通地址：https://cloud.weixin.qq.com）
- 本地安装 Python 3.x + Pillow 库
- 本地安装 Node.js 18+（仅部署时需要）

## 第一步：部署云托管服务

### 1.1 打包部署文件

将 skill 目录下 `scripts/` 里的以下文件打包为 `deploy.zip`：
- `server.js`
- `package.json`
- `Dockerfile`

### 1.2 创建云托管服务

1. 打开 https://cloud.weixin.qq.com/cloudrun
2. 点击「新建服务」
3. 选择「Express.js」模板
4. 上传 `deploy.zip`
5. 服务名称随意（如 `wechat-publisher`）
6. 点击「部署」，等待1-2分钟

### 1.3 获取服务地址

部署成功后，在服务详情页找到访问地址，格式类似：
```
https://{服务名}-{环境ID}.sh.run.tcloudbase.com
```

记住这个地址，后面要用。

## 第二步：配置免鉴权（核心步骤）

这一步是关键——配置后**不需要IP白名单**，一劳永逸。

### 2.1 开启开放接口服务

1. 进入云托管控制台
2. 左侧菜单找到「云调用」（不是「服务设置」！）
3. 打开「开放接口服务」开关
4. 点击「配置接口」

### 2.2 勾选接口

在弹窗中搜索并勾选以下8个接口：

| 接口路径 | 用途 |
|----------|------|
| `/cgi-bin/material/add_material` | 上传封面图 |
| `/cgi-bin/material/del_material` | 删除素材 |
| `/cgi-bin/draft/add` | 创建草稿（核心） |
| `/cgi-bin/draft/get` | 查询草稿 |
| `/cgi-bin/draft/update` | 更新草稿 |
| `/cgi-bin/draft/delete` | 删除草稿 |
| `/cgi-bin/token` | 获取token（免鉴权下用不到，勾上保险） |
| `/cgi-bin/media/uploadimg` | 上传正文配图 |

5. 点击「确认」保存

> 不需要扫码，点确认即保存。

### 2.3 验证免鉴权

部署完成后，访问以下地址验证：
```
GET https://{你的服务地址}/test
```

- 返回 `errcode: 43002`（require POST method）→ **免鉴权生效了**
- 返回 `errcode: 41001`（access_token missing）→ **免鉴权未生效**，检查第2.1步

## 第三步：本地配置

### 3.1 安装Python依赖

```bash
pip install Pillow requests
```

### 3.2 设置环境变量

将你的云托管服务地址设为环境变量：

**Windows (PowerShell)**：
```powershell
[System.Environment]::SetEnvironmentVariable("WX_PUBLISHER_URL", "https://你的服务地址.sh.run.tcloudbase.com", "User")
```

**macOS / Linux**：
```bash
echo 'export WX_PUBLISHER_URL="https://你的服务地址.sh.run.tcloudbase.com"' >> ~/.bashrc
source ~/.bashrc
```

设置后重启终端生效。

### 3.3 字体说明

PIL配图脚本默认使用 Windows 微软雅黑字体：
- 粗体：`C:/Windows/Fonts/msyhbd.ttc`
- 常规：`C:/Windows/Fonts/msyh.ttc`

**macOS 用户**需要修改字体路径为：
- 粗体：`/System/Library/Fonts/PingFang.ttc`
- 常规：`/System/Library/Fonts/PingFang.ttc`

**Linux 用户**需要安装中文字体：
```bash
sudo apt-get install fonts-wqy-microhei
# 字体路径：/usr/share/fonts/truetype/wqy/wqy-microhei.ttc
```

## 第四步：测试

### 4.1 健康检查
```bash
curl -s https://{你的服务地址}/health
```
应返回：`{"status":"ok","service":"wechat-publisher","version":"2.0.0-noauth"}`

### 4.2 推送测试文章

```bash
python scripts/publish_client.py \
  --server "https://你的服务地址.sh.run.tcloudbase.com" \
  --title "测试文章" \
  --digest "这是一篇测试文章" \
  --md test.md \
  --cover cover.png \
  --no-watermark
```

成功后会返回 `media_id`，去公众号后台草稿箱查看。

## 免鉴权原理（为什么不需要IP白名单）

传统方式：代码调 `/cgi-bin/token` 获取 access_token → 这个接口查IP白名单 → 云托管出口IP动态变化 → 每次都要改白名单。

免鉴权方式：代码**完全不调** token 接口，直接调业务API（`/cgi-bin/draft/add` 等），云托管平台自动在请求中注入 access_token。业务API走内网专线，**不查IP白名单**。

关键点：
- 代码中不出现 `access_token` 参数
- API地址用 `http://api.weixin.qq.com`（HTTP，不是HTTPS）
- 平台代理自动注入凭证

## 常见问题

### Q: 部署后推送返回502？
A: 云托管冷启动，先 `curl /health` 唤醒，等3秒再推。

### Q: /test 返回 41001？
A: 免鉴权未生效。检查「云调用→开放接口服务」是否开启，接口是否勾选。

### Q: 标题报错 45003？
A: 标题超过30字节（不是30字！）。中文占3字节，全角标点也占3字节。

### Q: 云托管收费吗？
A: 微信云托管有免费额度，个人用基本够。具体看 https://cloud.weixin.qq.com/cloudrun/pricing
