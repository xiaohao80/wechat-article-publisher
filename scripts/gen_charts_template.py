# -*- coding: utf-8 -*-
"""
PIL配图生成模板 - 微信公众号文章配图
=====================================
复制本文件到项目根目录，改名为 gen_charts_{主题}.py，按需修改内容。
运行: python gen_charts_{主题}.py

输出目录: {项目目录}/images/
字体: Windows用微软雅黑，macOS用PingFang，Linux用文泉微米黑
"""
import os
import sys
import platform
from PIL import Image, ImageDraw, ImageFont

# ===== 字体配置（自动适配操作系统）=====
def _get_font_paths():
    system = platform.system()
    if system == "Windows":
        return "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"
    elif system == "Darwin":  # macOS
        return "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"
    else:  # Linux
        return "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"

FONT_BOLD, FONT_REG = _get_font_paths()

# ===== 输出目录（自动检测项目根目录）=====
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_font(size, bold=True):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    except:
        return ImageFont.truetype(FONT_REG, size)


def draw_gradient_bg(w, h, top, bottom):
    """深色渐变背景"""
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        r = y / h
        c = tuple(int(top[i] * (1 - r) + bottom[i] * r) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)
    return img


def rrect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_grid(draw, w, h, spacing=50, color=(30, 40, 65)):
    """背景网格"""
    for x in range(0, w, spacing):
        draw.line([(x, 0), (x, h)], fill=color, width=1)
    for y in range(0, h, spacing):
        draw.line([(0, y), (w, y)], fill=color, width=1)


def draw_bar(draw, x, y, w, h, color, label, value, font_label, font_value):
    """画一个数据条"""
    rrect(draw, [x, y, x + w, y + h], 8, fill=color)
    # 数值
    draw.text((x + w // 2, y + h // 2), value, fill=(255, 255, 255),
              font=font_value, anchor="mm")
    # 标签
    draw.text((x + w // 2, y + h + 15), label, fill=(180, 190, 210),
              font=font_label, anchor="mm")


def draw_card(draw, x, y, w, h, title, items, font_title, font_item, accent=(100, 150, 255)):
    """画一个信息卡片"""
    rrect(draw, [x, y, x + w, y + h], 12, fill=(22, 32, 55),
          outline=accent, width=2)
    draw.text((x + 20, y + 18), title, fill=accent, font=font_title)
    for i, (label, value) in enumerate(items):
        yy = y + 55 + i * 32
        draw.text((x + 20, yy), label, fill=(160, 170, 190), font=font_item)
        draw.text((x + w - 20, yy), value, fill=(255, 255, 255),
                  font=font_item, anchor="rt")


# ============================================================
# 封面图 900x383 (2.35:1)
# ============================================================
def gen_cover():
    W, H = 900, 383
    img = draw_gradient_bg(W, H, (8, 12, 28), (20, 30, 55))
    draw = ImageDraw.Draw(img)
    draw_grid(draw, W, H)

    # 在这里画主题相关的视觉元素
    # 示例：大标题居中
    font_title = get_font(52)
    font_sub = get_font(24)
    draw.text((W // 2, H // 2 - 30), "文章主题", fill=(255, 255, 255),
              font=font_title, anchor="mm")
    draw.text((W // 2, H // 2 + 40), "副标题/关键数据", fill=(100, 200, 255),
              font=font_sub, anchor="mm")

    img.save(os.path.join(OUTPUT_DIR, "cover_template.png"))
    print("[OK] cover_template.png")


# ============================================================
# 正文图1：数据对比/条形图
# ============================================================
def gen_chart_1():
    W, H = 900, 600
    img = draw_gradient_bg(W, H, (12, 18, 35), (18, 25, 45))
    draw = ImageDraw.Draw(img)

    font_title = get_font(28)
    font_label = get_font(18)
    font_value = get_font(22)

    draw.text((W // 2, 40), "数据对比标题", fill=(255, 255, 255),
              font=font_title, anchor="mm")

    # 示例：3条对比数据
    data = [
        ("项目A", 75, (80, 200, 120)),
        ("项目B", 45, (255, 200, 80)),
        ("项目C", 30, (255, 100, 50)),
    ]
    bar_w = 180
    gap = 40
    start_x = (W - (len(data) * bar_w + (len(data) - 1) * gap)) // 2
    max_h = 350
    max_val = max(d[1] for d in data)

    for i, (label, val, color) in enumerate(data):
        x = start_x + i * (bar_w + gap)
        h = int(max_h * val / max_val)
        y = 450 - h
        draw_bar(draw, x, y, bar_w, h, color, label, f"{val}%",
                 font_label, font_value)

    img.save(os.path.join(OUTPUT_DIR, "chart_template_1.png"))
    print("[OK] chart_template_1.png")


# ============================================================
# 正文图2：信息卡片
# ============================================================
def gen_chart_2():
    W, H = 900, 500
    img = draw_gradient_bg(W, H, (12, 18, 35), (18, 25, 45))
    draw = ImageDraw.Draw(img)

    font_title = get_font(26)
    font_card_title = get_font(20)
    font_item = get_font(16)

    draw.text((W // 2, 35), "核心参数", fill=(255, 255, 255),
              font=font_title, anchor="mm")

    # 2x2 卡片布局
    card_w = 380
    card_h = 180
    cards = [
        ("参数组1", [("属性A", "值A"), ("属性B", "值B")], (100, 150, 255)),
        ("参数组2", [("属性C", "值C"), ("属性D", "值D")], (80, 200, 120)),
        ("参数组3", [("属性E", "值E"), ("属性F", "值F")], (255, 200, 80)),
        ("参数组4", [("属性G", "值G"), ("属性H", "值H")], (255, 100, 50)),
    ]
    for i, (title, items, color) in enumerate(cards):
        col = i % 2
        row = i // 2
        x = 50 + col * (card_w + 20)
        y = 80 + row * (card_h + 20)
        draw_card(draw, x, y, card_w, card_h, title, items,
                  font_card_title, font_item, accent=color)

    img.save(os.path.join(OUTPUT_DIR, "chart_template_2.png"))
    print("[OK] chart_template_2.png")


if __name__ == "__main__":
    gen_cover()
    gen_chart_1()
    gen_chart_2()
    # 按需添加 gen_chart_3(), gen_chart_4()
    print(f"\nAll charts generated to: {OUTPUT_DIR}")
