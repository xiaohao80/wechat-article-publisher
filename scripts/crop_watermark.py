from PIL import Image
import os

"""
去除AI生成图片底部水印——首选方案：直接裁剪底部100px
适用于 ImageGen / DALL-E 生成的带"图片由AI生成"水印的图片
"""

def crop_watermark(img_path, out_path, crop_height=100):
    img = Image.open(img_path).convert('RGB')
    w, h = img.size
    new_h = max(1, h - crop_height)
    cropped = img.crop((0, 0, w, new_h))
    cropped.save(out_path, 'PNG')
    print(f"  {w}x{h} -> {w}x{new_h} -> {out_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python crop_watermark.py <image1> [image2 ...] [--dir <directory>] [--height N]")
        print("  --dir     : process all .png files in directory")
        print("  --height  : pixels to crop from bottom (default 100)")
        sys.exit(1)
    
    crop_height = 100
    files = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--height":
            crop_height = int(sys.argv[i+1])
            i += 2
        elif arg == "--dir":
            d = sys.argv[i+1]
            for f in sorted(os.listdir(d)):
                if f.endswith('.png') and '_crop' not in f and '_clean' not in f:
                    files.append(os.path.join(d, f))
            i += 2
        else:
            files.append(arg)
            i += 1
    
    for inp in files:
        out = os.path.join(os.path.dirname(inp), 
                          os.path.basename(inp).replace('.png', '_crop.png'))
        print(f"Processing {inp} ...")
        crop_watermark(inp, out, crop_height)
    
    print("Done.")
