"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DocInfo {
  filename: string;
  type: string;
  category: string;
  chunks: number;
}

interface Stats {
  total_chunks: number;
  documents: number;
  by_type: Record<string, number>;
  by_category: Record<string, number>;
}

const TYPE_LABEL: Record<string, string> = {
  polished: "精排版",
  original: "原文",
  note: "精读笔记",
  guide: "导读",
  summary: "摘要",
  knowledge: "知识条目",
  moc: "索引",
};

const TYPE_COLORS: Record<string, string> = {
  polished: "#c9a84c",
  original: "#7a9e7e",
  note: "#8a7ab5",
  guide: "#5a9ec9",
  summary: "#c97a5a",
  knowledge: "#6a8a5a",
  moc: "#8a8a8a",
};

export default function KnowledgeBase() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [analyzeOn, setAnalyzeOn] = useState(true);  // ✨ 一键分析归纳开关
  const [analyzeResult, setAnalyzeResult] = useState<{ summary?: string; guide?: string; keywords?: string[] } | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/kb/stats`);
      if (res.ok) setStats(await res.json());
    } catch {
      // 静默
    }
  }, []);

  const loadDocs = useCallback(async (q = "", tf = "") => {
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (q) params.set("q", q);
      if (tf) params.set("type_filter", tf);
      const res = await fetch(`${API_URL}/kb/documents?${params}`);
      if (res.ok) {
        const data = await res.json();
        setDocs(data.documents || []);
        setTotal(data.total || 0);
      }
    } catch {
      // 静默
    }
  }, []);

  useEffect(() => {
    loadStats();
    loadDocs();
  }, [loadStats, loadDocs]);

  // 上传文件（单文件，兼容拖拽和选择；analyze=一键分析归纳）
  const uploadFile = async (file: File) => {
    setUploading(true);
    setUploadMsg("");
    setAnalyzeResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      if (analyzeOn) form.append("analyze", "true");
      const res = await fetch(`${API_URL}/ingest/file`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (res.ok) {
        const analyzeNote = data.analyze ? " + ✨自动归纳" : "";
        setUploadMsg(`✅ ${file.name} 入库成功（${data.chunks_count || "?"} 块${analyzeNote}）`);
        if (data.analyze) setAnalyzeResult(data.analyze);
        loadStats();
        loadDocs();
      } else {
        setUploadMsg(`❌ ${data.detail || "入库失败"}`);
      }
    } catch {
      setUploadMsg("❌ 上传失败：后端不可达");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  };

  // 统计图表（简单横向条）
  const maxType = stats ? Math.max(...Object.values(stats.by_type)) : 1;

  return (
    <main className="kb-page">
      <header className="kb-header">
        <a href="/" className="kb-back">← 返回对话</a>
        <h1>📚 知识库管理</h1>
        {stats && (
          <span className="kb-summary">
            {stats.documents} 个文档 · {stats.total_chunks.toLocaleString()} 块
          </span>
        )}
      </header>

      {/* 统计面板 */}
      {stats && (
        <section className="kb-stats">
          <div className="stat-cards">
            <div className="stat-card">
              <div className="stat-num">{stats.documents}</div>
              <div className="stat-label">文档数</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{stats.total_chunks.toLocaleString()}</div>
              <div className="stat-label">向量块数</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">
                {(stats.by_category.background || 0).toLocaleString()}
              </div>
              <div className="stat-label">背景文献块</div>
            </div>
          </div>

          <div className="type-dist">
            <p className="section-title">层级分布（type）</p>
            {Object.entries(stats.by_type).map(([type, count]) => (
              <div key={type} className="type-bar-row">
                <span className="type-bar-label">
                  {TYPE_LABEL[type] || type}
                </span>
                <div className="type-bar-track">
                  <div
                    className="type-bar-fill"
                    style={{
                      width: `${(count / maxType) * 100}%`,
                      background: TYPE_COLORS[type] || "#c9a84c",
                    }}
                  />
                </div>
                <span className="type-bar-count">{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 上传区 */}
      <section
        className={`upload-zone ${dragOver ? "dragging" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <div className="upload-inner">
          <div className="upload-icon">📤</div>
          <p>拖拽 PDF / Markdown / TXT 文件到此处入库</p>
          <label className="upload-btn">
            选择文件
            <input
              type="file"
              accept=".pdf,.md,.markdown,.txt"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadFile(f);
                e.target.value = "";
              }}
              disabled={uploading}
            />
          </label>
          <label className="analyze-toggle">
            <input
              type="checkbox"
              checked={analyzeOn}
              onChange={(e) => setAnalyzeOn(e.target.checked)}
            />
            ✨ 一键分析归纳（摘要/导读/关键词 → 自动入笔记层）
          </label>
          {uploading && <p className="upload-status">⏳ 处理中（向量化 + 分析归纳约 1-2 分钟）...</p>}
          {uploadMsg && <p className="upload-status">{uploadMsg}</p>}
          {analyzeResult && (
            <div className="analyze-result">
              <p className="analyze-title">✨ 自动归纳结果（已入笔记层，可被概览类问题检索）</p>
              {analyzeResult.summary && <p><b>摘要：</b>{analyzeResult.summary}</p>}
              {analyzeResult.guide && <p><b>导读：</b>{analyzeResult.guide}</p>}
              {analyzeResult.keywords && analyzeResult.keywords.length > 0 && (
                <p className="analyze-kws">
                  <b>关键词：</b>
                  {analyzeResult.keywords.map((k) => (
                    <span key={k} className="analyze-kw">{k}</span>
                  ))}
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* 文档列表 */}
      <section className="kb-docs">
        <div className="kb-toolbar">
          <input
            type="text"
            className="kb-search"
            placeholder="搜索文件名..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              loadDocs(e.target.value, typeFilter);
            }}
          />
          <select
            className="kb-filter"
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              loadDocs(search, e.target.value);
            }}
          >
            <option value="">全部层级</option>
            {Object.entries(TYPE_LABEL).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <span className="kb-total">共 {total} 个文档</span>
        </div>

        <div className="doc-table">
          {docs.map((d) => (
            <div key={d.filename} className="doc-row">
              <div className="doc-name" title={d.filename}>
                {d.filename.replace(/\.(md|pdf)$/, "")}
              </div>
              <span className="doc-type" style={{ background: (TYPE_COLORS[d.type] || "#888") + "33", color: TYPE_COLORS[d.type] || "#888" }}>
                {TYPE_LABEL[d.type] || d.type}
              </span>
              {d.category === "background" && (
                <span className="doc-cat">背景</span>
              )}
              <span className="doc-chunks">{d.chunks.toLocaleString()} 块</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
