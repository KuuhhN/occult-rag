"use client";

import { useEffect, useState } from "react";

interface TarotCard {
  card_id: number;
  name_cn: string;
  name_en: string;
  arcana: string;
  suit: string;
  reversed: boolean;
  interpretation: string;
}

interface Source {
  filename: string;
  type: string;
  score: number | null;
}

interface DrawResult {
  cards: TarotCard[];
  sources: Source[];
  question: string;
  overall: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** 牌面图路径：major-XX.jpg / minor-XXX.jpg（无图时 fallback 到文字牌面） */
function cardImageUrl(card: TarotCard): string {
  const arc = card.arcana === "major" ? "major" : "minor";
  const num = card.arcana === "major" ? card.card_id : card.card_id;
  return `/images/tarot/${arc}/${arc}-${String(num).padStart(card.arcana === "major" ? 2 : 3, "0")}.jpg`;
}

export default function TarotPage() {
  const [count, setCount] = useState(1);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DrawResult | null>(null);
  const [error, setError] = useState("");
  const [imageFailed, setImageFailed] = useState<Set<number>>(new Set());
  const [flippedIds, setFlippedIds] = useState<Set<number>>(new Set());

  // 点击 toggle：卡背 ↔ 卡面（揭示时解读淡入；再点翻回看卡背）
  const revealCard = (id: number) => {
    setFlippedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  async function draw() {
    setLoading(true);
    setError("");
    setResult(null);
    setImageFailed(new Set());
    try {
      const resp = await fetch(`${API}/tarot/draw`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count, question: question.trim() }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: DrawResult = await resp.json();
      setResult(data);
    } catch (e) {
      setError(`抽牌失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  const markImageFailed = (id: number) => {
    setImageFailed((prev) => new Set(prev).add(id));
  };

  return (
    <div className="tarot-page">
      <header className="kb-header">
        <a href="/" className="kb-back">← 返回对话</a>
        <h1>🔮 塔罗抽牌</h1>
        <p className="kb-sub">牌意由 RAG 从知识库（塔罗冥想等书籍）检索生成，有据可依</p>
      </header>

      <main className="tarot-main">
        {/* 控制区 */}
        <section className="tarot-controls glass-card">
          <div className="tarot-count">
            <span className="tarot-label">牌阵</span>
            <button
              className={`tarot-count-btn ${count === 1 ? "active" : ""}`}
              onClick={() => setCount(1)}
              disabled={loading}
            >
              单张
            </button>
            <button
              className={`tarot-count-btn ${count === 3 ? "active" : ""}`}
              onClick={() => setCount(3)}
              disabled={loading}
            >
              三张
            </button>
          </div>
          <input
            className="setting-input tarot-question"
            placeholder="问卜的问题（可选），如：我最近该注意什么"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={loading}
            maxLength={100}
          />
          <button className="sidebar-btn primary tarot-draw-btn" onClick={draw} disabled={loading}>
            {loading ? "洗牌中…" : "✦ 抽牌"}
          </button>
        </section>

        {error && <p className="tarot-error">{error}</p>}

        {/* 洗牌动画：单抽 1 张牌背，三抽 3 张 */}
        {loading && (
          <div className={`tarot-loading ${count === 1 ? "single" : ""}`} aria-label="洗牌中">
            <div className="card-back">🜃</div>
            {count > 1 && <div className="card-back delay-1">🜂</div>}
            {count > 1 && <div className="card-back delay-2">🜁</div>}
          </div>
        )}

        {/* 结果：3D 翻牌展示 */}
        {result && !loading && (
          <div className="tarot-result">
            {result.question && <p className="tarot-question-line">问卜：{result.question}</p>}
            <div className={`tarot-grid ${result.cards.length === 1 ? "single" : ""}`}>
              {result.cards.map((c, i) => {
                const img = cardImageUrl(c);
                const failed = imageFailed.has(c.card_id);
                return (
                  <article key={c.card_id} className="tarot-flip-wrap">
                    <div
                      className={`tarot-flip ${flippedIds.has(c.card_id) ? "flipped" : ""} ${c.reversed ? "is-reversed" : ""}`}
                      onClick={() => revealCard(c.card_id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") revealCard(c.card_id); }}
                      title={flippedIds.has(c.card_id) ? c.name_cn : "点击揭示卡面"}
                    >
                      {/* 卡背：大阿卡纳（JOJO 原画）用独立紫色 JOJO 风格 */}
                      <div className={`flip-face flip-back ${c.arcana === "major" ? "jojo-back" : ""}`}>
                        <div className="flip-back-design">{c.arcana === "major" ? "J" : "✦"}</div>
                        {c.arcana === "major" && <span className="flip-back-tag">JOJO</span>}
                      </div>
                      {/* 牌面 */}
                      <div className="flip-face flip-front">
                        {!failed ? (
                          <img
                            src={img}
                            alt={`${c.name_cn} ${c.reversed ? "逆位" : "正位"}`}
                            className="tarot-card-img"
                            loading="lazy"
                            onError={() => markImageFailed(c.card_id)}
                          />
                        ) : (
                          <div className="tarot-card-text-fallback">
                            <span className="tarot-card-no">
                              {c.arcana === "major" ? "大阿卡纳" : c.suit}
                            </span>
                            <h2 className="tarot-card-name">{c.name_cn}</h2>
                            <p className="tarot-card-en">{c.name_en}</p>
                          </div>
                        )}
                        <span className={`tarot-orientation ${c.reversed ? "rev" : ""}`}>
                          {c.reversed ? "逆位 ↕" : "正位"}
                        </span>
                      </div>
                    </div>
                    {/* 解读：揭示卡面时同步淡入 */}
                    <p className={`tarot-card-read ${flippedIds.has(c.card_id) ? "revealed" : ""}`}>
                      {c.interpretation}
                    </p>
                  </article>
                );
              })}
            </div>

            {result.overall && (
              <section className="tarot-overall glass-card">
                <h3 className="tarot-overall-title">✦ 综合解读</h3>
                <p className="tarot-overall-text">{result.overall}</p>
              </section>
            )}

            {result.sources.length > 0 && (
              <details className="tarot-sources glass-card">
                <summary>📜 检索来源（{result.sources.length}）</summary>
                <ul>
                  {result.sources.map((s, i) => (
                    <li key={i}>
                      {s.filename || "未知来源"}
                      <span className="source-score">{s.score !== null ? s.score.toFixed(2) : "BM25"}</span>
                      <span className="source-type">{s.type}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
