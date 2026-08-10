# -*- coding: utf-8 -*-
"""综合神秘学图库扩展：从 4 本新书提取插图（魔法/占星类）

输出：frontend/public/images/alchemy/{book_slug}/{page:03d}-{idx}.jpg
合并进 metadata.json（含 category 分类）
过滤：小图（短边<120px）丢弃；白底噪点过滤
"""
import fitz
import json
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images", "alchemy")
META = os.path.join(OUT, "metadata.json")

# (slug, pdf, book_title, category)
BOOKS = [
    ("greek-lamellae", "E:/obsidian/occult-vault/02-文献库/经典文献/Greek Magical Lamellae.pdf",
     "希腊魔法薄片（Greek Magical Lamellae）", "魔法实践"),
    ("lesser-key", "E:/obsidian/occult-vault/02-文献库/经典文献/The Lesser Key of Solomon.pdf",
     "所罗门小钥匙（The Lesser Key of Solomon）", "魔法实践"),
    ("seven-spheres", "E:/obsidian/occult-vault/02-文献库/经典文献/Seven Spheres.pdf",
     "七行星界（Seven Spheres）", "占星术"),
    ("graeco-egyptian", "E:/obsidian/occult-vault/02-文献库/经典文献/Graeco-Egyptian Magick.pdf",
     "希腊-埃及魔法（Graeco-Egyptian Magick）", "魔法实践"),
]
MIN_EDGE = 120


def is_noise(pix) -> bool:
    """简单噪点过滤：整图过小或纯色占比过高"""
    try:
        # 采样判断：四个角和中心
        w, h = pix.width, pix.height
        pts = [(w // 4, h // 4), (3 * w // 4, h // 4), (w // 4, 3 * h // 4), (3 * w // 4, 3 * h // 4), (w // 2, h // 2)]
        samples = []
        for (x, y) in pts:
            samples.append(pix.pixel(x, y))
        # 全同色 → 纯色噪点
        if len(set(samples)) == 1:
            return True
    except Exception:
        pass
    return False


def extract(book_slug, pdf_path, book_title, category):
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
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if pix.width < MIN_EDGE or pix.height < MIN_EDGE:
                    continue
                if is_noise(pix):
                    continue
                fname = f"{pno:03d}-{idx}.jpg"
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
                    "page_type": "插图",
                    "category": category,
                })
            except Exception as e:
                print(f"  [skip] p{pno} img{idx}: {e}", file=__import__("sys").stderr)
    doc.close()
    return meta


def main():
    # 保留现有 metadata
    existing = json.load(open(META, encoding="utf-8")) if os.path.exists(META) else []
    existing_ids = {m["id"] for m in existing}
    all_meta = list(existing)

    for slug, path, title, cat in BOOKS:
        if not os.path.exists(path):
            print(f"[warn] 不存在: {path}")
            continue
        print(f"提取 {title} ...")
        m = extract(slug, path, title, cat)
        new = [x for x in m if x["id"] not in existing_ids]
        all_meta.extend(new)
        print(f"  -> 新提取 {len(new)} 张（去重后）")

    json.dump(all_meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"总计 {len(all_meta)} 张（原 {len(existing)} + 新 {len(all_meta) - len(existing)}）")


if __name__ == "__main__":
    main()
