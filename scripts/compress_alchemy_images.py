# -*- coding: utf-8 -*-
"""
炼金图像压缩：PNG → JPEG(质量82, 最长边1000px)，体积降 10-20 倍
同时标记 page_type：宽高比>1.3 的竖版大图为"整页扫描"，其余为"插图"
"""
import json
import os
from PIL import Image

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images", "alchemy")
MAX_EDGE = 1000
JPEG_Q = 82


def compress(m):
    src = os.path.join(OUT, m["book"], os.path.basename(m["file"]))
    im = Image.open(src)
    w, h = im.size
    scale = MAX_EDGE / max(w, h)
    if scale < 1:
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    # 转换 JPEG
    if im.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    dst = os.path.join(OUT, m["book"], os.path.basename(m["file"]).rsplit(".", 1)[0] + ".jpg")
    im.save(dst, "JPEG", quality=JPEG_Q)
    os.remove(src)  # 删 PNG 原图
    m["file"] = m["file"].rsplit(".", 1)[0] + ".jpg"
    m["page_type"] = "整页" if (max(w, h) / min(w, h) > 1.3 and min(w, h) > 700) else "插图"
    m["width"], m["height"] = im.size
    return dst


def main():
    meta_path = os.path.join(OUT, "metadata.json")
    meta = json.load(open(meta_path, encoding="utf-8"))
    for m in meta:
        compress(m)
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(os.path.getsize(os.path.join(OUT, m["book"], os.path.basename(m["file"]))) for m in meta)
    n_ill = sum(1 for m in meta if m["page_type"] == "插图")
    print(f"完成：{len(meta)} 张，插图 {n_ill} / 整页 {len(meta)-n_ill}，总大小 {total//1024//1024} MB")


if __name__ == "__main__":
    main()
