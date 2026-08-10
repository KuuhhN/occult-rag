"use client";

// 炼金图像版块：图库墙（按书分组）→ 点击弹解读卡片（多模态 RAG 成果展示）
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

type ImgMeta = {
  id: string;
  book: string;
  book_title: string;
  page: number;
  file: string;
  width: number;
  height: number;
  page_type: string;
  summary?: string;
};

type Interp = {
  summary?: string;
  interpretation?: string;
  keywords?: string[];
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BOOKS: Record<string, string> = {
  "real-alchemy": "Real Alchemy",
  "manly-hall": "Manly Hall 手稿",
  alchemy: "炼金术",
};

export default function AlchemyPage() {
  const [images, setImages] = useState<ImgMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "插图" | "整页">("all");
  const [book, setBook] = useState<string>("all");
  const [selected, setSelected] = useState<ImgMeta | null>(null);
  const [interp, setInterp] = useState<Interp | null>(null);
  const [interpLoading, setInterpLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "500" });
      if (filter !== "all") params.set("page_type", filter);
      if (book !== "all") params.set("book", book);
      const r = await fetch(`${API}/alchemy/images?${params}`);
      const d = await r.json();
      setImages(d.items ?? []);
    } catch {
      setImages([]);
    } finally {
      setLoading(false);
    }
  }, [filter, book]);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = async (img: ImgMeta) => {
    setSelected(img);
    setInterp(null);
    setInterpLoading(true);
    try {
      const r = await fetch(`${API}/alchemy/images/${img.id}`);
      const d = await r.json();
      setInterp(d);
    } catch {
      setInterp(null);
    } finally {
      setInterpLoading(false);
    }
  };

  // 支持 URL 直达：/alchemy?img=<id> 时自动打开对应图解读
  const searchParams = useSearchParams();
  const targetId = searchParams.get("img");
  const autoOpenedRef = useRef(false);

  useEffect(() => {
    if (loading || !targetId || autoOpenedRef.current) return;
    autoOpenedRef.current = true;
    const target = images.find((m) => m.id === targetId);
    if (target) {
      openDetail(target);
    }
    // 只触发一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  const grouped = images.reduce<Record<string, ImgMeta[]>>((acc, m) => {
    (acc[m.book] ??= []).push(m);
    return acc;
  }, {});

  return (
    <main className="alchemy-page">
      <div className="alchemy-header">
        <a href="/" className="back-link">← 返回</a>
        <h1 className="occult-title">⚗️ 炼金图像</h1>
        <p className="subtitle">炼金术图像是理解贤者之石秘密的重要途径 — 图像 + AI 解读 + 文献互证</p>
      </div>

      <div className="alchemy-filters">
        <select value={filter} onChange={(e) => setFilter(e.target.value as any)} className="alchemy-select">
          <option value="all">全部类型</option>
          <option value="插图">插图</option>
          <option value="整页">整页</option>
        </select>
        <select value={book} onChange={(e) => setBook(e.target.value)} className="alchemy-select">
          <option value="all">全部书籍</option>
          {Object.entries(BOOKS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <span className="alchemy-count">{images.length} 张</span>
      </div>

      {loading ? (
        <p className="alchemy-empty">加载中…</p>
      ) : Object.keys(grouped).length === 0 ? (
        <p className="alchemy-empty">没有匹配的图像</p>
      ) : (
        Object.entries(grouped).map(([bk, items]) => (
          <section key={bk} className="alchemy-book">
            <h2 className="alchemy-book-title">{BOOKS[bk] ?? bk} · {items.length} 张</h2>
            <div className="alchemy-grid">
              {items.map((m) => (
                <button key={m.id} className="alchemy-card" onClick={() => openDetail(m)} title={m.summary || m.id}>
                  <img src={`${API}/static/alchemy/${m.file.replace("/images/alchemy/", "")}`}
                    alt={m.summary || m.id} loading="lazy" />
                  <span className="alchemy-card-page">p{m.page}</span>
                  {m.summary && <span className="alchemy-card-summary">{m.summary.slice(0, 26)}</span>}
                </button>
              ))}
            </div>
          </section>
        ))
      )}

      {selected && (
        <div className="alchemy-modal" onClick={() => setSelected(null)}>
          <div className="alchemy-modal-body" onClick={(e) => e.stopPropagation()}>
            <button className="alchemy-modal-close" onClick={() => setSelected(null)}>✕</button>
            <img src={`${API}/static/alchemy/${selected.file.replace("/images/alchemy/", "")}`}
              alt={selected.id} className="alchemy-modal-img" />
            <div className="alchemy-modal-info">
              <h3>{BOOKS[selected.book] ?? selected.book} · 第 {selected.page} 页</h3>
              {interpLoading ? (
                <p className="alchemy-empty">解读中…</p>
              ) : interp ? (
                <>
                  <p className="alchemy-interp-summary">{interp.summary}</p>
                  <p className="alchemy-interp">{interp.interpretation}</p>
                  {interp.keywords && interp.keywords.length > 0 && (
                    <div className="alchemy-keywords">
                      {interp.keywords.map((k) => <span key={k} className="alchemy-keyword">{k}</span>)}
                    </div>
                  )}
                </>
              ) : (
                <p className="alchemy-empty">暂无解读（后台生成中）</p>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
