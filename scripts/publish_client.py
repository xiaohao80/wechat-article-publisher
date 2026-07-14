# -*- coding: utf-8 -*-
"""
本地发布客户端 - 调用云托管服务推送文章到草稿箱
================================================
用法:
  python publish_client.py --server https://xxx.sh.run.tcloudbase.com \
      --title "文章标题" \
      --digest "文章摘要" \
      --md article.md \
      --cover cover.png \
      --images img1.png img2.png img3.png

  # 不去水印（PIL生成的图没有AI水印）
  python publish_client.py --server https://xxx.sh.run.tcloudbase.com \
      --title "标题" --digest "摘要" --md article.md --cover cover.png --no-watermark

  # 带作者
  python publish_client.py ... --author "作者名"

  # 也可以把 server 地址存到环境变量，省得每次传:
  set WX_PUBLISHER_URL=https://xxx.sh.run.tcloudbase.com
  python publish_client.py --title "标题" --digest "摘要" --md article.md --cover cover.png
"""
import os
import sys
import argparse
import requests
import urllib3

# 跳过SSL验证（云托管内网/代理环境兼容）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main():
    parser = argparse.ArgumentParser(description="推送文章到微信公众号草稿箱")
    parser.add_argument("--server", default=os.environ.get("WX_PUBLISHER_URL", ""),
                        help="云托管服务地址（也可用环境变量 WX_PUBLISHER_URL）")
    parser.add_argument("--title", required=True, help="文章标题（不超过30字节）")
    parser.add_argument("--digest", required=True, help="文章摘要（不超过64字节）")
    parser.add_argument("--author", default="", help="作者名（可选）")
    parser.add_argument("--md", required=True, help="Markdown文件路径")
    parser.add_argument("--cover", required=True, help="封面图路径（2.35:1）")
    parser.add_argument("--images", nargs="*", default=[], help="正文配图路径列表")
    parser.add_argument("--no-watermark", action="store_true", help="不去水印")
    args = parser.parse_args()

    # 校验
    if not args.server:
        print("ERROR: 请通过 --server 或环境变量 WX_PUBLISHER_URL 指定服务地址")
        sys.exit(1)

    title_bytes = len(args.title.encode("utf-8"))
    digest_bytes = len(args.digest.encode("utf-8"))
    if title_bytes > 30:
        print(f"ERROR: 标题超过30字节（当前{title_bytes}字节）: {args.title}")
        sys.exit(1)
    if digest_bytes > 64:
        print(f"ERROR: 摘要超过64字节（当前{digest_bytes}字节）: {args.digest}")
        sys.exit(1)

    # 读取markdown
    if not os.path.exists(args.md):
        print(f"ERROR: Markdown文件不存在: {args.md}")
        sys.exit(1)
    with open(args.md, "r", encoding="utf-8") as f:
        md_text = f.read()

    # 校验图片文件
    if not os.path.exists(args.cover):
        print(f"ERROR: 封面图不存在: {args.cover}")
        sys.exit(1)
    for img_path in args.images:
        if not os.path.exists(img_path):
            print(f"ERROR: 配图不存在: {img_path}")
            sys.exit(1)

    # 构建请求
    url = f"{args.server.rstrip('/')}/publish"
    data = {
        "title": args.title,
        "digest": args.digest,
        "author": args.author,
        "markdown": md_text,
        "remove_watermark": "false" if args.no_watermark else "true",
    }

    files = []
    open_files = []
    try:
        cover_f = open(args.cover, "rb")
        open_files.append(cover_f)
        files.append(("cover", (os.path.basename(args.cover), cover_f, "image/png")))

        for img_path in args.images:
            f = open(img_path, "rb")
            open_files.append(f)
            files.append(("images", (os.path.basename(img_path), f, "image/png")))

        print(f"[INFO] 正在推送到 {url}")
        print(f"       标题: {args.title} ({title_bytes}字节)")
        print(f"       摘要: {args.digest} ({digest_bytes}字节)")
        print(f"       配图: 1封面 + {len(args.images)}张正文")
        print(f"       去水印: {'否' if args.no_watermark else '是'}")

        resp = requests.post(url, data=data, files=files, timeout=180, verify=False)

        try:
            result = resp.json()
        except Exception:
            print(f"\n[FAIL] 服务器返回非JSON响应 (HTTP {resp.status_code})")
            print(f"       响应前500字符: {resp.text[:500]}")
            sys.exit(1)

        if result.get("success"):
            print(f"\n[DONE] {result['message']}")
            print(f"        标题: {result.get('title', '')}")
            print(f"        media_id: {result.get('media_id', '')}")
        else:
            print(f"\n[FAIL] {result.get('error', '未知错误')}")
            if result.get("wechat_error"):
                print(f"        微信返回: {result.get('wechat_error')}")
            sys.exit(1)

    finally:
        for f in open_files:
            f.close()


if __name__ == "__main__":
    main()
