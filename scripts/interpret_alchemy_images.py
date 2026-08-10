# -*- coding: utf-8 -*-
"""
炼金图像解读：智谱 glm-4v-flash 批量解读炼金图
输出：frontend/public/images/alchemy/interpretations.json
    [{id, summary(短描述), interpretation(深度解读), keywords[]}]
断点续跑：已有解读的图跳过；限速 1.2s/张 避免限流
用法：python scripts/interpret_alchemy_images.py [limit]
"""
import base64
import json
import os
import sys
import time
import urllib.request

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4v-flash"
KEY = os.environ.get("ZHIPU_API_KEY", "")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images", "alchemy")
OUT_JSON = os.path.join(OUT_DIR, "interpretations.json")
PROMPT = (
    "这是一张炼金术/神秘学图像。请用中文输出：\n"
    "1) 一句话概括图像内容（30字内）\n"
    "2) 详细解读：图像中的符号、人物、容器、动物、天体等元素各自的炼金术含义，"
    "以及整体对应炼金术的哪个阶段（黑化nigredo/白化albedo/黄化citrinitas/红化rubedo）或核心概念（贤者之石/哲学家之蛋/衔尾蛇等），"
    "如果确定不了就如实说。200字左右。\n"
    "3) 提取3-5个关键词（炼金符号名，逗号分隔）\n"
    "格式：\n摘要：...\n解读：...\n关键词：...\n"
)


def understand(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = "image/jpeg" if path.lower().endswith(".jpg") else "image/png"
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": PROMPT},
            ],
        }],
        "max_tokens": 800,
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def parse(text: str) -> dict:
    """兼容多种格式：'摘要：xxx' 同行 / '概括：\nxxx' 跨行 / '### 3. 关键词：' 编号"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    summary, interp, kws = "", "", []

    def val_after(idx: int) -> str:
        """取第 idx 行冒号后的内容；为空则取下一行"""
        v = lines[idx].split("：", 1)[-1].strip() if "：" in lines[idx] else ""
        if not v and idx + 1 < len(lines) and not lines[idx + 1].startswith("#"):
            v = lines[idx + 1].strip()
        return v

    s_idx = k_idx = -1
    for i, l in enumerate(lines):
        if s_idx < 0 and ("概括" in l or "摘要" in l):
            s_idx = i
            summary = val_after(i).lstrip("#").strip()
        if "关键词" in l:
            k_idx = i
            kws = [k.strip() for k in val_after(i).split(",") if k.strip()]
    if s_idx >= 0 and k_idx > s_idx:
        body = lines[s_idx + 1:k_idx]
    elif s_idx >= 0:
        body = lines[s_idx + 1:]
    elif k_idx > 0:
        body = lines[:k_idx]
    else:
        body = lines
    # 去掉 '### 2. 详细解读' 这类标题行
    body = [l for l in body if not (l.startswith("#") or "详细解读" in l or "图像内容" in l)]
    interp = "\n".join(body).strip()
    if not interp:
        interp = text
    return {"summary": summary, "interpretation": interp, "keywords": kws}


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if not KEY:
        print("ERROR: ZHIPU_API_KEY 未设置"); sys.exit(1)
    meta = json.load(open(os.path.join(OUT_DIR, "metadata.json"), encoding="utf-8"))
    interps = {}
    if os.path.exists(OUT_JSON):
        interps = json.load(open(OUT_JSON, encoding="utf-8"))
    todo = [m for m in meta if m["id"] not in interps]
    if limit:
        todo = todo[:limit]
    print(f"待解读 {len(todo)} 张（已有 {len(interps)}）")
    for i, m in enumerate(todo, 1):
        path = os.path.join(OUT_DIR, m["book"], os.path.basename(m["file"]))
        try:
            text = understand(path)
            interps[m["id"]] = parse(text)
            print(f"[{i}/{len(todo)}] {m['id']} -> {interps[m['id']]['summary'][:40]}")
        except Exception as e:
            print(f"[{i}/{len(todo)}] {m['id']} FAIL: {e}", file=sys.stderr)
        json.dump(interps, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.2)  # 限速
    ok = sum(1 for m in meta if m["id"] in interps and interps[m["id"]].get("summary"))
    print(f"完成：{ok}/{len(meta)} 张有解读")


if __name__ == "__main__":
    main()
