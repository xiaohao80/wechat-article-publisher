#!/usr/bin/env python3
"""
小红书自动发布脚本 (xhs_publisher.py)
基于 Playwright 实现浏览器自动化，持久化登录态，支持图文笔记发布。

用法:
  # 检查登录状态
  python xhs_publisher.py check

  # 登录（弹出浏览器扫码）
  python xhs_publisher.py login

  # 发布笔记（直接发布）
  python xhs_publisher.py publish --title "标题" --content "正文" --images img1.png img2.png --topics 话题1 话题2

  # 从文件读取正文
  python xhs_publisher.py publish --title "标题" --content-file note.md --images img1.png --topics 话题1

  # 搜索笔记
  python xhs_publisher.py search "关键词"
"""

import asyncio
import os
import sys
import json
import argparse
import tempfile
from pathlib import Path

# ===== 配置 =====
BROWSER_DATA_DIR = os.path.expanduser("~/.xhs-browser-data")
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official&from=tab_switch"
HOME_URL = "https://www.xiaohongshu.com"
DEFAULT_TIMEOUT = 60000
VIEWPORT = {"width": 1280, "height": 800}
# 调试截图目录（默认当前目录，可用 --debug-dir 覆盖）
DEBUG_DIR = os.getcwd()

# ===== 浏览器管理 =====

class XHSBrowser:
    """小红书浏览器自动化管理器"""

    def __init__(self, debug_dir=None):
        self.playwright = None
        self.context = None
        self.page = None
        self.debug_dir = debug_dir or DEBUG_DIR

    def _debug_path(self, filename):
        """获取调试截图路径"""
        return os.path.join(self.debug_dir, filename)

    async def start(self, headless=False):
        """启动浏览器（持久化上下文，保存登录态）"""
        from playwright.async_api import async_playwright

        os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

        # 清理可能存在的锁文件
        for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
            lock_path = os.path.join(BROWSER_DATA_DIR, lock_file)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except:
                    pass

        self.playwright = await async_playwright().start()

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=headless,
            viewport=VIEWPORT,
            timeout=DEFAULT_TIMEOUT,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-infobars',
            ],
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
        )

        # 注入反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """)

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        self.page.set_default_timeout(DEFAULT_TIMEOUT)

    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def check_login(self):
        """检查登录状态"""
        try:
            if not self.page.url.startswith("https://www.xiaohongshu.com"):
                await self.page.goto(HOME_URL, timeout=DEFAULT_TIMEOUT)
                await asyncio.sleep(3)

            # 检查是否有"登录"按钮 → 未登录
            login_btn = await self.page.query_selector('.login-btn, [class*="login"]')
            if login_btn:
                login_text = await self.page.query_selector('text="登录"')
                if login_text:
                    return False, "未登录：页面有登录按钮"

            # 检查是否有用户头像/昵称 → 已登录
            user_el = await self.page.query_selector('.user-avatar, .side-bar .user, [class*="avatar"]')
            if user_el:
                return True, "已登录：检测到用户头像"

            # 如果 URL 跳转到了登录页
            if "login" in self.page.url.lower():
                return False, f"未登录：URL 跳转到登录页 ({self.page.url})"

            # 默认认为已登录（没找到登录按钮）
            return True, "可能已登录：未检测到登录按钮"

        except Exception as e:
            return False, f"检查登录状态出错: {e}"

    async def login(self):
        """登录流程：打开浏览器，等用户扫码"""
        try:
            await self.page.goto(HOME_URL, timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(3)

            logged_in, msg = await self.check_login()
            if logged_in:
                return True, f"已经登录了，不需要重复登录（{msg}）"

            print("\n" + "=" * 50)
            print("浏览器已打开小红书首页")
            print("请在浏览器中完成登录（扫码/手机号等）")
            print("登录成功后，脚本会自动检测并继续")
            print("=" * 50 + "\n")

            for i in range(60):
                await asyncio.sleep(5)
                logged_in, _ = await self.check_login()
                if logged_in:
                    return True, "登录成功！登录态已保存，下次无需重复登录"
                print(f"  等待登录中... ({(i+1)*5}s)", end="\r")

            return False, "等待登录超时（5分钟），请重试"

        except Exception as e:
            return False, f"登录过程出错: {e}"

    async def _find_publish_frame(self):
        """找到包含发布表单的 iframe frame 对象"""
        await asyncio.sleep(2)
        frames = self.page.frames
        print(f"  当前页面 frames: {[(f.url[:60]) for f in frames]}")
        for frame in frames:
            if 'publish' in frame.url or 'creator' in frame.url:
                print(f"  ✅ 找到发布表单 frame: {frame.url[:80]}")
                return frame
        for frame in frames:
            try:
                text = await frame.evaluate('document.body ? document.body.innerText : ""')
                if '上传图文' in text or '发布' in text:
                    print(f"  ✅ 通过内容找到 frame: {frame.url[:80]}")
                    return frame
            except:
                continue
        return None

    async def publish_note(self, title, content, image_paths, topics=None, draft=False):
        """发布图文笔记

        Args:
            title: 笔记标题（最多20字）
            content: 笔记正文
            image_paths: 图片路径列表
            topics: 话题标签列表（可选）
            draft: True=存草稿箱, False=直接发布
                   注意：草稿模式（暂存离开按钮）目前不可靠，建议用直接发布
        """
        try:
            # 1. 检查登录
            logged_in, msg = await self.check_login()
            if not logged_in:
                return False, f"未登录，请先执行 login 命令（{msg}）"

            # 2. 验证图片文件
            for img_path in image_paths:
                if not os.path.exists(img_path):
                    return False, f"图片不存在: {img_path}"

            # 3. 访问发布页面
            print("正在打开发布页面...")
            await self.page.goto(PUBLISH_URL, timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(5)

            # 4. 找到 iframe（整个发布表单都在 iframe 里）
            print("查找发布表单 iframe...")
            frame = await self._find_publish_frame()
            if not frame:
                await self.page.screenshot(path=self._debug_path("debug_no_frame.png"))
                return False, "找不到发布表单的 iframe，已截图 debug_no_frame.png"

            # 5. 在 iframe 内切换到"上传图文" tab
            print("切换到上传图文 tab...")
            try:
                clicked = await frame.evaluate('''() => {
                    const elements = document.querySelectorAll('*');
                    for (const el of elements) {
                        if (el.children.length === 0 && el.textContent.trim() === '上传图文') {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                if clicked:
                    await asyncio.sleep(3)
                    print("  ✅ 已切换到图文模式")
                else:
                    print("  ⚠️ 未找到上传图文 tab，可能已经是图文模式")
            except Exception as e:
                print(f"  切换tab时出错: {e}")
            await asyncio.sleep(2)

            # 6. 在 iframe 内上传图片（逐张上传，file input 不支持多文件）
            print(f"开始上传 {len(image_paths)} 张图片...")
            for i, img_path in enumerate(image_paths):
                print(f"  上传第 {i+1}/{len(image_paths)} 张: {os.path.basename(img_path)}")
                file_input = await frame.query_selector('input[type="file"]')
                if file_input:
                    await file_input.set_input_files(img_path)
                    await asyncio.sleep(3)
                    print(f"    ✅ 第 {i+1} 张上传完成")
                else:
                    return False, f"在 iframe 内找不到 file input（第{i+1}张）"
            print("  ✅ 所有图片上传完成")

            # 7. 在 iframe 内输入标题
            print(f"输入标题: {title}")
            title_input = await frame.query_selector(
                'input[placeholder*="标题"], textarea[placeholder*="标题"]'
            )
            if title_input:
                await title_input.click()
                await asyncio.sleep(0.3)
                await title_input.fill(title)
                await asyncio.sleep(1)
                print("  ✅ 标题已输入")
            else:
                await frame.screenshot(path=self._debug_path("debug_no_title.png"))
                return False, "在 iframe 内找不到标题输入框，已截图 debug_no_title.png"

            # 8. 在 iframe 内输入正文
            print("输入正文内容...")
            content_input = await frame.query_selector(
                'div[contenteditable="true"], textarea[placeholder*="输入正文"], [role="textbox"]'
            )
            if content_input:
                await content_input.click()
                await asyncio.sleep(0.5)
                await content_input.type(content)
                await asyncio.sleep(1)
                print("  ✅ 正文已输入")

                # 添加话题标签
                if topics:
                    print(f"添加 {len(topics)} 个话题标签...")
                    await content_input.type('\n\n')
                    for i, topic in enumerate(topics):
                        topic_text = f"#{topic}"
                        print(f"  输入话题: {topic_text}")
                        await content_input.type(topic_text)
                        await asyncio.sleep(2)

                        suggestion_clicked = False
                        suggestion_selectors = [
                            'div[class*="topic"] div[class*="item"]:first-child',
                            '.el-select-dropdown__item:first-child',
                            'div[role="option"]:first-child',
                            'li[role="option"]:first-child',
                        ]
                        for selector in suggestion_selectors:
                            try:
                                suggestion = await frame.query_selector(selector)
                                if suggestion and await suggestion.is_visible():
                                    await suggestion.click()
                                    await asyncio.sleep(1)
                                    suggestion_clicked = True
                                    break
                            except:
                                continue

                        if not suggestion_clicked:
                            await content_input.press('Enter')
                            await asyncio.sleep(0.5)

                        if i < len(topics) - 1:
                            await content_input.type(' ')
                            await asyncio.sleep(0.5)

                    print("  ✅ 话题标签添加完成")
            else:
                await frame.screenshot(path=self._debug_path("debug_no_content.png"))
                return False, "在 iframe 内找不到正文输入框，已截图 debug_no_content.png"

            # 9. 点击发布/暂存按钮
            action = "暂存" if draft else "发布"
            print(f"准备点击{action}按钮...")
            await frame.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(3)

            await self.page.screenshot(path=self._debug_path("debug_before_publish.png"))
            print("  已保存发布前截图")

            publish_clicked = False

            # 获取 <xhs-publish-btn> Vue 组件的 rect
            # 这是一个自定义 Web Component，内部按钮不在 light DOM 里
            rect = await frame.evaluate('''() => {
                const el = document.querySelector('xhs-publish-btn');
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height};
            }''')
            print(f"  xhs-publish-btn rect: {rect}")

            # 点击位置比例：
            # draft=True  → 左侧"暂存离开"按钮 (~25%)
            # draft=False → 右侧"发布"按钮 (~65%)
            # ⚠️ position 参数是像素偏移量，不是0-1比例！
            click_ratio = 0.25 if draft else 0.65

            # 策略A: frame.locator + 像素 position 点击容器
            if rect:
                print(f"  策略A: frame.locator 点击容器 ({action}位置, ratio={click_ratio})...")
                try:
                    click_px_x = int(rect['w'] * click_ratio)
                    click_px_y = int(rect['h'] * 0.5)
                    print(f"    position 像素: ({click_px_x}, {click_px_y})")
                    await frame.locator('xhs-publish-btn').click(
                        position={'x': click_px_x, 'y': click_px_y},
                        force=True,
                        timeout=10000
                    )
                    publish_clicked = True
                    print(f"  ✅ 策略A成功: frame.locator + 像素位置")
                except Exception as e:
                    print(f"  策略A失败: {e}")

            # 策略B: page.mouse.click 绝对坐标
            if not publish_clicked and rect:
                print(f"  策略B: page.mouse.click 绝对坐标 ({action})...")
                try:
                    abs_x = int(rect['x'] + rect['w'] * click_ratio)
                    abs_y = int(rect['y'] + rect['h'] * 0.5)
                    print(f"    绝对坐标: ({abs_x}, {abs_y})")
                    await self.page.mouse.move(abs_x, abs_y)
                    await asyncio.sleep(0.3)
                    await self.page.mouse.click(abs_x, abs_y)
                    publish_clicked = True
                    print(f"  ✅ 策略B成功: page.mouse.click")
                except Exception as e:
                    print(f"  策略B失败: {e}")

            # 策略C: frame.evaluate 穿透 shadow DOM 查找内部按钮
            if not publish_clicked:
                print(f"  策略C: 查找 shadow DOM 内部按钮 ({action})...")
                target_text = "暂存" if draft else "发布"
                try:
                    result = await frame.evaluate('''(targetText) => {
                        const host = document.querySelector('xhs-publish-btn');
                        if (!host) return {found: false, reason: 'no host'};
                        if (host.shadowRoot) {
                            const btns = host.shadowRoot.querySelectorAll('button, [role="button"], div[class*="btn"], .publish, .submit, .save, .draft');
                            for (const btn of btns) {
                                if (btn.textContent.includes(targetText)) {
                                    btn.click();
                                    return {found: true, via: 'shadow', tag: btn.tagName, text: btn.textContent.trim()};
                                }
                            }
                        }
                        const innerBtns = host.querySelectorAll('button, [role="button"], div[class*="btn"]');
                        for (const btn of innerBtns) {
                            if (btn.textContent.includes(targetText)) {
                                btn.click();
                                return {found: true, via: 'inner-dom', tag: btn.tagName, text: btn.textContent.trim()};
                            }
                        }
                        return {found: false, reason: 'no inner button', hasShadow: !!host.shadowRoot, innerBtnCount: innerBtns.length};
                    }''', target_text)
                    if result.get('found'):
                        publish_clicked = True
                        print(f"  ✅ 策略C成功: {result}")
                    else:
                        print(f"  策略C失败: {result}")
                except Exception as e:
                    print(f"  策略C出错: {e}")

            await asyncio.sleep(6)

            # 10. 检查结果
            action_past = "暂存" if draft else "发布"
            print(f"检查{action_past}结果...")
            await self.page.screenshot(path=self._debug_path("debug_after_publish.png"))

            success_keywords = ["暂存成功", "保存成功"] if draft else ["发布成功"]
            for keyword in success_keywords:
                success_el = await frame.query_selector(f'text="{keyword}"')
                if not success_el:
                    success_el = await self.page.query_selector(f'text="{keyword}"')
                if success_el:
                    return True, f"{action_past}成功！"

            for selector in ['.error-message', '.toast-message', '.el-message--error', '.el-message__content']:
                error_el = await frame.query_selector(selector)
                if not error_el:
                    error_el = await self.page.query_selector(selector)
                if error_el:
                    error_text = await error_el.text_content()
                    return False, f"{action_past}失败: {error_text}"

            if not draft:
                current_url = self.page.url
                if "manage" in current_url.lower() or "success" in current_url.lower():
                    return True, f"发布成功（已跳转: {current_url}）"

                frame_url = frame.url
                if "manage" in frame_url.lower():
                    return True, f"发布成功（frame已跳转: {frame_url}）"

            if draft:
                if "publish" in self.page.url:
                    return True, f"暂存成功！（页面仍在发布页，未报错）"

            return False, f"{action_past}结果不确定，已截图 debug_after_publish.png，请人工检查"

        except Exception as e:
            try:
                await self.page.screenshot(path=self._debug_path("publish_error.png"))
                return False, f"发布出错: {e}（已截图 publish_error.png）"
            except:
                return False, f"发布出错: {e}"

    async def search_notes(self, keyword, limit=10):
        """搜索笔记"""
        try:
            logged_in, msg = await self.check_login()
            if not logged_in:
                return False, f"未登录（{msg}）"

            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
            await self.page.goto(search_url, timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(5)

            notes = []
            note_items = await self.page.query_selector_all('.note-item, [class*="note"] a[href*="/explore/"]')

            for item in note_items[:limit]:
                try:
                    title_el = await item.query_selector('.title, [class*="title"], span')
                    title = await title_el.text_content() if title_el else ""

                    link = await item.get_attribute('href')
                    if link and not link.startswith("http"):
                        link = f"https://www.xiaohongshu.com{link}"

                    if title or link:
                        notes.append({"title": title.strip(), "url": link})
                except:
                    continue

            return True, notes

        except Exception as e:
            return False, f"搜索出错: {e}"


# ===== CLI 命令 =====

async def cmd_check(args):
    browser = XHSBrowser(debug_dir=args.debug_dir)
    try:
        print("启动浏览器...")
        await browser.start(headless=False)
        logged_in, msg = await browser.check_login()
        status = "✅" if logged_in else "❌"
        print(f"\n{status} 登录状态: {msg}")
        return 0 if logged_in else 1
    finally:
        await browser.close()

async def cmd_login(args):
    browser = XHSBrowser(debug_dir=args.debug_dir)
    try:
        print("启动浏览器...")
        await browser.start(headless=False)
        success, msg = await browser.login()
        status = "✅" if success else "❌"
        print(f"\n{status} {msg}")
        return 0 if success else 1
    finally:
        await browser.close()

async def cmd_publish(args):
    browser = XHSBrowser(debug_dir=args.debug_dir)
    try:
        print("启动浏览器...")
        await browser.start(headless=False)

        content = args.content
        if args.content_file:
            with open(args.content_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            print(f"从文件读取正文: {args.content_file} ({len(content)} 字)")

        topics = args.topics if args.topics else None
        success, msg = await browser.publish_note(
            title=args.title,
            content=content,
            image_paths=args.images,
            topics=topics,
            draft=args.draft
        )
        status = "✅" if success else "❌"
        action = "暂存" if args.draft else "发布"
        print(f"\n{status} {action}: {msg}")
        return 0 if success else 1
    finally:
        await browser.close()

async def cmd_search(args):
    browser = XHSBrowser(debug_dir=args.debug_dir)
    try:
        print("启动浏览器...")
        await browser.start(headless=False)
        success, result = await browser.search_notes(args.keyword, args.limit)
        if success:
            print(f"\n✅ 搜索 '{args.keyword}' 结果（{len(result)} 条）:")
            for i, note in enumerate(result, 1):
                print(f"  {i}. {note['title']}")
                print(f"     {note['url']}")
            return 0
        else:
            print(f"\n❌ {result}")
            return 1
    finally:
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description="小红书自动发布工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 公共参数
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--debug-dir", default=os.getcwd(), help="调试截图保存目录（默认当前目录）")

    # check
    subparsers.add_parser("check", help="检查登录状态", parents=[common])

    # login
    subparsers.add_parser("login", help="登录小红书（扫码）", parents=[common])

    # publish
    pub_parser = subparsers.add_parser("publish", help="发布图文笔记", parents=[common])
    pub_parser.add_argument("--title", required=True, help="笔记标题（最多20字）")
    pub_parser.add_argument("--content", help="笔记正文（与 --content-file 二选一）")
    pub_parser.add_argument("--content-file", help="从文件读取笔记正文（避免命令行转义问题）")
    pub_parser.add_argument("--images", nargs="+", required=True, help="图片路径（可多张）")
    pub_parser.add_argument("--topics", nargs="*", help="话题标签（可选）")
    pub_parser.add_argument("--draft", action="store_true", help="存草稿箱（实验性，可能不可靠）")

    # search
    search_parser = subparsers.add_parser("search", help="搜索笔记", parents=[common])
    search_parser.add_argument("keyword", help="搜索关键词")
    search_parser.add_argument("--limit", type=int, default=10, help="返回结果数量")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "check": cmd_check,
        "login": cmd_login,
        "publish": cmd_publish,
        "search": cmd_search,
    }

    return asyncio.run(commands[args.command](args))


if __name__ == "__main__":
    sys.exit(main())
