/**
 * 微信公众号草稿箱推送服务 - 微信云托管版 (Node.js / Express)
 * =========================================================
 * 部署到微信云托管后，自动免鉴权调用公众号API，无需配置IP白名单。
 *
 * 接口:
 *   POST /publish          - 推送文章到草稿箱
 *   POST /menu/create      - 创建自定义菜单
 *   GET  /menu/get         - 获取当前菜单
 *   GET  /menu/delete      - 删除所有菜单
 *   POST /article/publish  - 发布草稿文章（草稿→正式发布）
 *   POST /draft/list       - 获取草稿列表
 *   POST /material/list    - 获取素材列表
 *   GET  /health           - 健康检查
 *   GET  /test             - 免鉴权诊断
 *   GET  /                 - 首页信息
 */
const express = require('express');
const multer  = require('multer');
const axios   = require('axios');
const FormData = require('form-data');
const sharp   = require('sharp');
const crypto  = require('crypto');
const path    = require('path');
const fs      = require('fs');

const app = express();

// 云托管内用http（内网专线免证书），本地调试用https
const API_BASE = process.env.WX_API_BASE || 'http://api.weixin.qq.com';

// 跳过SSL验证（云托管内网代理兼容）
const https = require('https');
axios.defaults.httpsAgent = new https.Agent({ rejectUnauthorized: false });

// multer配置：内存存储，不落盘
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 } // 10MB
});

// body解析
app.use(express.json());
app.use(express.urlencoded({ extended: true }));


// ========== 去AI水印 ==========

async function removeWatermark(imgBuffer) {
  /**
   * 去除AI生成图片右下角"图片由AI生成"水印
   * 算法与Python版remove_watermark_v6一致：
   * 1. 扫描右下角60%宽×15%高区域
   * 2. 取上方紧邻区域深色像素作为背景色
   * 3. 找亮度差>60且自身亮度>100的文字像素
   * 4. 取外接矩形+4px padding，用背景色覆盖
   */
  let meta;
  try {
    meta = await sharp(imgBuffer).metadata();
  } catch (e) {
    console.log('[WARN] 图片解析失败，跳过去水印');
    return imgBuffer;
  }

  const w = meta.width;
  const h = meta.height;

  // 获取raw RGB像素
  const raw = await sharp(imgBuffer)
    .removeAlpha()
    .raw()
    .toBuffer();

  // 扫描区域
  const scanW = Math.floor(w * 0.60);
  const scanH = Math.floor(h * 0.15);
  const scanLeft = w - scanW;
  const scanTop  = h - scanH;

  // 取扫描区上方紧邻区域的深色背景色
  const sampleTop    = Math.max(0, scanTop - 40);
  const sampleBottom = scanTop;
  const colorCount = {};
  for (let y = sampleTop; y < sampleBottom; y++) {
    for (let x = scanLeft; x < w; x++) {
      const idx = (y * w + x) * 3;
      const r = raw[idx], g = raw[idx + 1], b = raw[idx + 2];
      if (Math.max(r, g, b) < 60) {
        const key = `${r},${g},${b}`;
        colorCount[key] = (colorCount[key] || 0) + 1;
      }
    }
  }
  let bgR = 0, bgG = 0, bgB = 0;
  let maxCount = 0;
  for (const [key, count] of Object.entries(colorCount)) {
    if (count > maxCount) {
      maxCount = count;
      [bgR, bgG, bgB] = key.split(',').map(Number);
    }
  }

  // 找水印文字像素
  const bgLum = (bgR + bgG + bgB) / 3;
  let minX = w, maxX = 0, minY = h, maxY = 0;
  let found = false;
  for (let y = scanTop; y < h; y++) {
    for (let x = scanLeft; x < w; x++) {
      const idx = (y * w + x) * 3;
      const r = raw[idx], g = raw[idx + 1], b = raw[idx + 2];
      const lum = (r + g + b) / 3;
      if (lum - bgLum > 60 && lum > 100) {
        found = true;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }

  if (!found) {
    console.log('  [水印] 未检测到水印，跳过');
    return imgBuffer;
  }

  // 扩展边缘
  const pad = 4;
  minX = Math.max(0, minX - pad);
  maxX = Math.min(w - 1, maxX + pad);
  minY = Math.max(0, minY - pad);
  maxY = Math.min(h - 1, maxY + pad);

  const rectW = maxX - minX + 1;
  const rectH = maxY - minY + 1;

  // 用SVG矩形覆盖水印区域
  const svgOverlay = Buffer.from(
    `<svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">` +
    `<rect x="${minX}" y="${minY}" width="${rectW}" height="${rectH}" fill="rgb(${bgR},${bgG},${bgB})"/>` +
    `</svg>`
  );

  const result = await sharp(imgBuffer)
    .composite([{ input: svgOverlay, top: 0, left: 0 }])
    .png()
    .toBuffer();

  console.log(`  [水印] 已去除 (${minX},${minY})-(${maxX},${maxY})`);
  return result;
}


// ========== 微信API ==========

async function uploadPermanentMaterial(imgBuffer, filename = 'cover.png') {
  /** 上传永久素材（封面图）— 云托管免鉴权，无需access_token */
  const url = `${API_BASE}/cgi-bin/material/add_material?type=image`;
  const form = new FormData();
  form.append('media', imgBuffer, { filename, contentType: 'image/png' });

  const resp = await axios.post(url, form, {
    headers: form.getHeaders(),
    maxContentLength: Infinity,
    maxBodyLength: Infinity,
    timeout: 60000
  });
  if (!resp.data.media_id) {
    throw new Error(`上传封面图失败: ${JSON.stringify(resp.data)}`);
  }
  console.log(`[OK] 封面图上传成功: ${resp.data.media_id}`);
  return resp.data.media_id;
}


async function uploadContentImage(imgBuffer, filename = 'content.png') {
  /** 上传正文配图 — 云托管免鉴权，无需access_token */
  const url = `${API_BASE}/cgi-bin/media/uploadimg`;
  const form = new FormData();
  form.append('media', imgBuffer, { filename, contentType: 'image/png' });

  const resp = await axios.post(url, form, {
    headers: form.getHeaders(),
    maxContentLength: Infinity,
    maxBodyLength: Infinity,
    timeout: 60000
  });
  if (!resp.data.url) {
    throw new Error(`上传正文配图失败: ${JSON.stringify(resp.data)}`);
  }
  console.log(`[OK] 正文配图上传成功: ${filename}`);
  return resp.data.url;
}


async function createDraft(thumbMediaId, content, title, digest, author = '') {
  /** 创建草稿 — 云托管免鉴权，无需access_token */
  const url = `${API_BASE}/cgi-bin/draft/add`;
  const article = {
    title,
    content,
    digest,
    content_source_url: '',
    need_open_comment: 0,
    only_fans_can_comment: 0,
    thumb_media_id: thumbMediaId
  };
  if (author) {
    article.author = author;
  }
  const payload = { articles: [article] };

  // Node.js默认UTF-8，不需要ensure_ascii
  const resp = await axios.post(url, payload, {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    timeout: 60000
  });
  if (!resp.data.media_id) {
    throw new Error(`创建草稿失败: ${JSON.stringify(resp.data)}`);
  }
  console.log(`[OK] 草稿创建成功: ${resp.data.media_id}`);
  return resp.data.media_id;
}


// ========== Markdown转HTML ==========

function mdToHtml(mdText, imageUrls) {
  /**
   * 将Markdown转换为微信公众号兼容的HTML
   * imageUrls: Array of [desc, url]
   * 支持占位符: [配图1] [配图1：xxx] [配图1:xxx] [配图1 xxx]
   */
  // 正则替换所有占位符变体
  mdText = mdText.replace(/\[配图(\d+)[：:\s][^\]]*\]/g, '__IMG_$1__');
  mdText = mdText.replace(/\[配图(\d+)\]/g, '__IMG_$1__');

  const htmlParts = [];
  let listItems = [];
  let inList = false;

  function flushList() {
    if (listItems.length > 0) {
      htmlParts.push("<ul style='margin: 12px 0; padding-left: 24px;'>");
      for (const item of listItems) {
        htmlParts.push(`<li style='margin: 6px 0; line-height: 1.7; color: #3f3f3f;'>${item}</li>`);
      }
      htmlParts.push('</ul>');
      listItems = [];
    }
    inList = false;
  }

  const lines = mdText.split('\n');
  for (let line of lines) {
    const stripped = line.trim();

    if (!stripped) {
      if (inList) flushList();
      continue;
    }

    if (stripped.startsWith('# ')) {
      if (inList) flushList();
      const t = stripped.slice(2).trim();
      htmlParts.push(`<h1 style='font-size: 22px; color: #1a1a1a; margin: 24px 0 16px; font-weight: 700; text-align: center;'>${t}</h1>`);
    } else if (stripped.startsWith('## ')) {
      if (inList) flushList();
      const h2 = stripped.slice(3).trim();
      htmlParts.push(`<h2 style='font-size: 18px; color: #2c2c2c; margin: 28px 0 12px; font-weight: 700; border-left: 4px solid #1976d2; padding-left: 12px;'>${h2}</h2>`);
    } else if (stripped.startsWith('### ')) {
      if (inList) flushList();
      const h3 = stripped.slice(4).trim();
      htmlParts.push(`<h3 style='font-size: 16px; color: #3a3a3a; margin: 20px 0 10px; font-weight: 600;'>${h3}</h3>`);
    } else if (stripped.startsWith('> ')) {
      if (inList) flushList();
      const quote = stripped.slice(2).trim();
      htmlParts.push(`<blockquote style='border-left: 4px solid #ff9800; background: #fff8e1; padding: 12px 16px; margin: 14px 0; color: #5d4037; font-size: 15px; line-height: 1.7;'>${quote}</blockquote>`);
    } else if (stripped === '---') {
      if (inList) flushList();
      htmlParts.push("<hr style='border: none; border-top: 1px dashed #ddd; margin: 24px 0;'/>");
    } else if (/^__IMG_\d+__$/.test(stripped)) {
      if (inList) flushList();
      const num = parseInt(stripped.match(/\d+/)[0]);
      if (num >= 1 && num <= imageUrls.length) {
        const url = imageUrls[num - 1][1];
        htmlParts.push(`<p style='text-align: center; margin: 20px 0;'><img src='${url}' style='max-width: 100%; height: auto; border-radius: 6px;'/></p>`);
      }
    } else if (stripped.startsWith('- ') || /^\d+\.\s/.test(stripped)) {
      inList = true;
      const content = stripped.replace(/^-\s*|^\d+\.\s*/, '');
      listItems.push(content);
    } else {
      if (inList) flushList();
      let text = stripped;
      text = text.replace(/\*\*(.+?)\*\*/g, "<strong style='color: #d32f2f; font-weight: 600;'>$1</strong>");
      htmlParts.push(`<p style='font-size: 16px; line-height: 1.85; color: #3f3f3f; margin: 12px 0; text-align: justify;'>${text}</p>`);
    }
  }

  if (inList) flushList();

  return htmlParts.join('');
}


// ========== HTTP接口 ==========

app.post('/publish', upload.fields([
  { name: 'cover', maxCount: 1 },
  { name: 'images', maxCount: 10 }
]), async (req, res) => {
  try {
    const title = req.body.title || '';
    const digest = req.body.digest || '';
    const author = req.body.author || '';
    const mdText = req.body.markdown || '';
    const removeWm = (req.body.remove_watermark || 'true').toLowerCase() === 'true';

    // 字节数校验
    const titleBytes = Buffer.byteLength(title, 'utf-8');
    const digestBytes = Buffer.byteLength(digest, 'utf-8');
    if (titleBytes > 30) {
      return res.status(400).json({ success: false, error: `标题超过30字节（当前${titleBytes}字节）` });
    }
    if (digestBytes > 64) {
      return res.status(400).json({ success: false, error: `摘要超过64字节（当前${digestBytes}字节）` });
    }

    // 获取封面图
    if (!req.files || !req.files.cover || req.files.cover.length === 0) {
      return res.status(400).json({ success: false, error: '缺少封面图（cover字段）' });
    }
    let coverBuffer = req.files.cover[0].buffer;

    // 去水印
    if (removeWm) {
      console.log('[INFO] 处理封面图去水印...');
      coverBuffer = await removeWatermark(coverBuffer);
    }

    // 获取正文配图
    const contentImages = (req.files.images || []);
    const imageDataList = [];
    for (let i = 0; i < contentImages.length; i++) {
      let imgBuf = contentImages[i].buffer;
      if (removeWm) {
        console.log(`[INFO] 处理正文配图${i + 1}去水印...`);
        imgBuf = await removeWatermark(imgBuf);
      }
      imageDataList.push(imgBuf);
    }

    // 1. 云托管免鉴权模式：无需获取access_token，平台自动注入
    console.log(`[INFO] 标题: ${title} (${titleBytes}字节)`);
    console.log(`[INFO] 摘要: ${digest} (${digestBytes}字节)`);
    console.log(`[INFO] 云托管免鉴权模式，跳过token获取`);

    // 2. 上传封面图
    const thumbMediaId = await uploadPermanentMaterial(coverBuffer, 'cover.png');

    // 3. 上传正文配图
    const imageUrls = [];
    for (let i = 0; i < imageDataList.length; i++) {
      const url = await uploadContentImage(imageDataList[i], `image_${i + 1}.png`);
      imageUrls.push([`配图${i + 1}`, url]);
    }

    // 4. 构建HTML
    const html = mdToHtml(mdText, imageUrls);
    console.log(`[INFO] HTML生成完成，长度: ${html.length} 字符`);

    // 5. 创建草稿
    const mediaId = await createDraft(thumbMediaId, html, title, digest, author);

    res.json({
      success: true,
      media_id: mediaId,
      title,
      digest,
      message: '文章已成功推送到草稿箱'
    });

  } catch (err) {
    console.error(`[ERROR] ${err.message}`);
    if (err.response) {
      console.error(`[ERROR DATA] ${JSON.stringify(err.response.data)}`);
      console.error(`[ERROR STATUS] ${err.response.status}`);
    }
    res.status(500).json({
      success: false,
      error: err.message,
      wechat_error: err.response ? err.response.data : null
    });
  }
});


app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'wechat-publisher', runtime: 'nodejs', version: '3.0.0-noauth' });
});


// ========== 免鉴权诊断 ==========

app.get('/test', async (req, res) => {
  /**
   * 测试云托管免鉴权是否生效
   * 调用 /cgi-bin/draft/get（已授权接口）传一个假media_id
   * 如果返回 errcode 41001 → access_token missing → 免鉴权没生效
   * 如果返回其他 errcode（如 40007 invalid media_id）→ 免鉴权生效了
   */
  try {
    const url = `${API_BASE}/cgi-bin/draft/get?media_id=test_12345`;
    console.log(`[TEST] 调用: ${url}`);
    const resp = await axios.get(url, { timeout: 15000 });
    console.log(`[TEST] 微信返回: ${JSON.stringify(resp.data)}`);

    const errcode = resp.data.errcode;
    if (errcode === 41001) {
      res.json({
        success: false,
        mode: '免鉴权未生效',
        detail: 'access_token missing (errcode 41001)',
        wechat_response: resp.data,
        suggestion: '检查云托管控制台「云调用→开放接口服务」是否已开启并配置了接口权限'
      });
    } else if (errcode === 40007 || errcode === 40004) {
      res.json({
        success: true,
        mode: '免鉴权已生效',
        detail: 'access_token 已自动注入，API正常响应（media_id无效是预期的，因为我们传了假ID测试）',
        wechat_response: resp.data
      });
    } else if (!errcode || errcode === 0) {
      res.json({
        success: true,
        mode: '免鉴权已生效',
        detail: 'API调用成功',
        wechat_response: resp.data
      });
    } else {
      res.json({
        success: true,
        mode: '免鉴权可能已生效（收到非41001错误）',
        detail: `errcode=${errcode}, errmsg=${resp.data.errmsg}`,
        wechat_response: resp.data
      });
    }
  } catch (err) {
    console.error(`[TEST ERROR] ${err.message}`);
    if (err.response) {
      console.error(`[TEST ERROR DATA] ${JSON.stringify(err.response.data)}`);
    }
    res.status(500).json({
      success: false,
      error: err.message,
      error_data: err.response ? err.response.data : null
    });
  }
});


// ========== 自定义菜单 ==========

app.post('/menu/create', async (req, res) => {
  /**
   * 创建自定义菜单
   * Body: { menu: { button: [...] } }
   * 或直接传 button 数组: { buttons: [...] }
   */
  try {
    const menuData = req.body.menu || { button: req.body.buttons || [] };
    if (!menuData.button || menuData.button.length === 0) {
      return res.status(400).json({ success: false, error: '缺少菜单数据（menu.button 或 buttons）' });
    }

    const url = `${API_BASE}/cgi-bin/menu/create`;
    console.log(`[MENU] 创建菜单，按钮数: ${menuData.button.length}`);

    const resp = await axios.post(url, menuData, {
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      timeout: 30000
    });

    console.log(`[MENU] 微信返回: ${JSON.stringify(resp.data)}`);

    if (resp.data.errcode === 0 || !resp.data.errcode) {
      res.json({ success: true, message: '菜单创建成功', wechat_response: resp.data });
    } else {
      res.json({ success: false, error: `菜单创建失败: errcode=${resp.data.errcode}, errmsg=${resp.data.errmsg}`, wechat_response: resp.data });
    }
  } catch (err) {
    console.error(`[MENU CREATE ERROR] ${err.message}`);
    res.status(500).json({ success: false, error: err.message, wechat_error: err.response ? err.response.data : null });
  }
});


app.get('/menu/get', async (req, res) => {
  /** 获取当前菜单配置 */
  try {
    const url = `${API_BASE}/cgi-bin/menu/get`;
    const resp = await axios.get(url, { timeout: 15000 });
    res.json({ success: true, menu: resp.data });
  } catch (err) {
    console.error(`[MENU GET ERROR] ${err.message}`);
    res.status(500).json({ success: false, error: err.message, wechat_error: err.response ? err.response.data : null });
  }
});


app.get('/menu/delete', async (req, res) => {
  /** 删除所有自定义菜单 */
  try {
    const url = `${API_BASE}/cgi-bin/menu/delete`;
    const resp = await axios.get(url, { timeout: 15000 });
    console.log(`[MENU DELETE] 微信返回: ${JSON.stringify(resp.data)}`);
    res.json({ success: true, message: '菜单已删除', wechat_response: resp.data });
  } catch (err) {
    console.error(`[MENU DELETE ERROR] ${err.message}`);
    res.status(500).json({ success: false, error: err.message, wechat_error: err.response ? err.response.data : null });
  }
});


// ========== 文章发布 ==========

app.post('/article/publish', async (req, res) => {
  /**
   * 发布草稿箱中的文章（草稿→正式发布）
   * Body: { media_id: "草稿的media_id" }
   * 注意：发布后需要审核，审核通过后文章正式上线
   */
  try {
    const mediaId = req.body.media_id;
    if (!mediaId) {
      return res.status(400).json({ success: false, error: '缺少 media_id（草稿的media_id）' });
    }

    const url = `${API_BASE}/cgi-bin/freepublish/submit`;
    console.log(`[PUBLISH] 发布文章，media_id: ${mediaId}`);

    const resp = await axios.post(url, { media_id: mediaId }, {
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      timeout: 30000
    });

    console.log(`[PUBLISH] 微信返回: ${JSON.stringify(resp.data)}`);

    if (resp.data.errcode === 0 || !resp.data.errcode) {
      res.json({
        success: true,
        publish_id: resp.data.publish_id,
        message: '文章已提交发布，等待审核',
        wechat_response: resp.data
      });
    } else {
      res.json({
        success: false,
        error: `发布失败: errcode=${resp.data.errcode}, errmsg=${resp.data.errmsg}`,
        wechat_response: resp.data
      });
    }
  } catch (err) {
    console.error(`[PUBLISH ERROR] ${err.message}`);
    res.status(500).json({ success: false, error: err.message, wechat_error: err.response ? err.response.data : null });
  }
});


// ========== 草稿列表 ==========

app.post('/draft/list', async (req, res) => {
  /**
   * 获取草稿列表
   * Body: { offset: 0, count: 20, no_content: 1 }
   */
  try {
    const offset = req.body.offset || 0;
    const count = req.body.count || 20;
    const noContent = req.body.no_content !== undefined ? req.body.no_content : 1;

    const url = `${API_BASE}/cgi-bin/draft/batchget_material`;
    const payload = { offset, count, no_content: noContent };

    const resp = await axios.post(url, payload, {
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      timeout: 30000
    });

    console.log(`[DRAFT LIST] 返回 ${resp.data.item_count || 0} 篇草稿`);
    res.json({ success: true, data: resp.data });
  } catch (err) {
    console.error(`[DRAFT LIST ERROR] ${err.message}`);
    res.status(500).json({ success: false, error: err.message, wechat_error: err.response ? err.response.data : null });
  }
});


// ========== 素材列表 ==========

app.post('/material/list', async (req, res) => {
  /**
   * 获取素材列表
   * Body: { type: "image", offset: 0, count: 20 }
   */
  try {
    const type = req.body.type || 'image';
    const offset = req.body.offset || 0;
    const count = req.body.count || 20;

    const url = `${API_BASE}/cgi-bin/material/batchget_material`;
    const payload = { type, offset, count };

    const resp = await axios.post(url, payload, {
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      timeout: 30000
    });

    res.json({ success: true, data: resp.data });
  } catch (err) {
    console.error(`[MATERIAL LIST ERROR] ${err.message}`);
    res.status(500).json({ success: false, error: err.message, wechat_error: err.response ? err.response.data : null });
  }
});


app.get('/', (req, res) => {
  res.json({
    service: 'wechat-publisher',
    runtime: 'Node.js / Express',
    version: '3.0.0-noauth',
    endpoints: {
      'POST /publish': '推送文章到草稿箱',
      'POST /menu/create': '创建自定义菜单',
      'GET  /menu/get': '获取当前菜单',
      'GET  /menu/delete': '删除所有菜单',
      'POST /article/publish': '发布草稿文章（草稿→正式发布）',
      'POST /draft/list': '获取草稿列表',
      'POST /material/list': '获取素材列表',
      'GET  /health': '健康检查',
      'GET  /test': '免鉴权诊断'
    }
  });
});


// 启动服务
const PORT = process.env.PORT || 80;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`[wechat-publisher] 服务已启动，监听端口 ${PORT}`);
});
