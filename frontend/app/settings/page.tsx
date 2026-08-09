"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Settings() {
  const [topK, setTopK] = useState(5);
  const [includeBackground, setIncludeBackground] = useState(false);
  const [retrievalMode, setRetrievalMode] = useState<string>("hybrid");
  const [modelInfo, setModelInfo] = useState<string>("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const tk = localStorage.getItem("rag_top_k");
    const bg = localStorage.getItem("rag_include_background");
    const rm = localStorage.getItem("rag_retrieval_mode");
    if (tk) setTopK(parseInt(tk, 10));
    if (bg) setIncludeBackground(bg === "1");
    if (rm) setRetrievalMode(rm);
  }, []);

  const save = () => {
    localStorage.setItem("rag_top_k", String(topK));
    localStorage.setItem("rag_include_background", includeBackground ? "1" : "0");
    localStorage.setItem("rag_retrieval_mode", retrievalMode);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <main className="settings-page">
      <header className="settings-header">
        <a href="/" className="kb-back">← 返回对话</a>
        <h1>⚙️ 设置</h1>
      </header>

      <section className="settings-card">
        <h2>检索参数</h2>

        <div className="setting-row">
          <div className="setting-info">
            <div className="setting-name">检索文档数（top_k）</div>
            <div className="setting-desc">每次回答检索多少个相关文档块（1-20）</div>
          </div>
          <input
            type="number"
            min={1}
            max={20}
            value={topK}
            onChange={(e) => setTopK(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
            className="setting-input"
          />
        </div>

        <div className="setting-row">
          <div className="setting-info">
            <div className="setting-name">包含背景文献</div>
            <div className="setting-desc">
              默认排除（荷马史诗/神谱等背景文献检索优先级低）；开启后参与检索
            </div>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={includeBackground}
              onChange={(e) => setIncludeBackground(e.target.checked)}
            />
            <span className="slider" />
          </label>
        </div>

        <div className="setting-row">
          <div className="setting-info">
            <div className="setting-name">检索模式</div>
            <div className="setting-desc">
              hybrid：向量语义 + BM25 关键词 RRF 融合（推荐）；vector：纯向量
            </div>
          </div>
          <select
            className="setting-input"
            value={retrievalMode}
            onChange={(e) => setRetrievalMode(e.target.value)}
          >
            <option value="hybrid">混合检索（向量 + BM25）</option>
            <option value="vector">纯向量检索</option>
          </select>
        </div>

        <button className="save-btn" onClick={save}>
          {saved ? "✅ 已保存" : "保存设置"}
        </button>
      </section>

      <section className="settings-card">
        <h2>系统信息</h2>
        <div className="setting-row">
          <div className="setting-info">
            <div className="setting-name">知识库状态</div>
            <div className="setting-desc">
              <a href="/kb" className="kb-back">查看知识库管理 →</a>
            </div>
          </div>
        </div>
        <div className="setting-row">
          <div className="setting-info">
            <div className="setting-name">API 端点</div>
            <div className="setting-desc">{API_URL}</div>
          </div>
        </div>
      </section>
    </main>
  );
}
