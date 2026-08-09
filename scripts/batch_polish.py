"""批量生成精排版：对 02-文献库 全部 OCR 原文跑 format_ocr

用法: python scripts/batch_polish.py
输出: <vault>/02-文献库/经典文献/<书名>_精排版.md
"""
import os
import sys
import subprocess
from pathlib import Path

VAULT = os.environ.get("OCCULT_VAULT", r"E:\obsidian\occult-vault")
FORMAT_OCR = os.environ.get(
    "FORMAT_OCR", r"C:\Users\KUHN\AppData\Local\Temp\occult-ingest\occult-ingest\format_ocr.py"
)


def main():
    lit_dir = Path(VAULT) / "02-文献库" / "经典文献"
    if not lit_dir.is_dir():
        print(f"❌ 目录不存在: {lit_dir}")
        sys.exit(1)

    originals = sorted(lit_dir.glob("*_原文.md"))
    if not originals:
        print("❌ 未找到 *_原文.md")
        sys.exit(1)

    print(f"发现 {len(originals)} 篇原文，开始批量生成精排版...")
    ok = 0
    skipped = 0
    for orig in originals:
        book_name = orig.name[: -len("_原文.md")]  # 书名（去掉 _原文.md）
        out = orig.with_name(f"{book_name}_精排版.md")

        if out.exists():
            print(f"  [SKIP] 已存在: {out.name}")
            skipped += 1
            continue

        try:
            subprocess.run(
                [sys.executable, FORMAT_OCR, str(orig), str(out),
                 "--title", book_name],
                check=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120,
            )
            print(f"  [OK] {orig.name} → {out.name}")
            ok += 1
        except subprocess.CalledProcessError as e:
            print(f"  [FAIL] {orig.name}: {e.stderr[:200]}")
        except Exception as e:
            print(f"  [FAIL] {orig.name}: {e}")

    print(f"\n完成: {ok} 篇生成, {skipped} 篇已存在跳过")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
