# -*- coding: utf-8 -*-
"""
炼金图像提取：pymupdf 从炼金术 PDF 抠图
输出：frontend/public/images/alchemy/{book_slug}/{page:03d}-{idx}.png + metadata.json
过滤：小图（<30KB 或 短边<120px）视为装饰/噪点丢弃
用法：python scripts/extract_alchemy_images.py [pdf路径...]  （默认扫描 vault 炼金书）
"""
import fitz
import json
import os
import sys

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images", "alchemy")
BOOKS = [
    ("real-alchemy", "E:/obsidian/occult-vault/02-文献库/经典文献/Real Alchemy.pdf", "Real Alchemy（罗伯特·艾伦·巴特利特）"),
    ("manly-hall", "E:/obsidian/occult-vault/02-文献库/经典文献/Manly Hall 炼金术手稿合集.pdf", "Manly Hall 炼金术手稿合集"),
    ("alchemy", "E:/obsidian/occult-vault/02-文献库/经典文献/炼金术.pdf", "炼金术"),
]
MIN_SIZE = (120, 120)  # 短边阈值，过滤噪点


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("（", "").replace("）", "")


def extract(book_slug: str, pdf_path: str, book_title: str) -> list:
    doc = fitz.open(pdf_path)
    book_dir = os.path.join(OUT, book_slug)
    os.makedirs(book_dir, exist_ok=True)
    meta = []
    for pno in range(doc.page_count):
        page = doc[pno]
        imgs = page.get_images(full=True)
        for idx, img in enumerate(imgs):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n > 4:  # CMYK 转 RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if pix.width < MIN_SIZE[0] or pix.height < MIN_SIZE[1]:
                    continue
                # 过滤纯白/纯色背景占绝大多数的图（噪点）
                fname = f"{pno:03d}-{idx}.png"
                fpath = os.path.join(book_dir, fname)
                pix.save(fpath)
                meta.append({
                    "id": f"{book_slug}/{fname}",
                    "book": book_slug,
                    "book_title": book_title,
                    "page": pno + 1,
                    "file": f"/images/alchemy/{book_slug}/{fname}",
                    "width": pix.width,
                    "height": pix.height,
                })
            except Exception as e:
                print(f"  [skip] p{pno} img{idx}: {e}", file=sys.stderr)
    doc.close()
    return meta


def main():
    targets = sys.argv[1:] or [b[0] for b in BOOKS]
    all_meta = []
    for slug, path, title in BOOKS:
        if slug not in targets:
            continue
        if not os.path.exists(path):
            print(f"[warn] 不存在: {path}")
            continue
        print(f"提取 {title} ...")
        m = extract(slug, path, title)
        print(f"  -> {len(m)} 张图")
        all_meta.extend(m)
    with open(os.path.join(OUT, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=1)
    print(f"总计 {len(all_meta)} 张，metadata.json 已写")


if __name__ == "__main__":
    main()
