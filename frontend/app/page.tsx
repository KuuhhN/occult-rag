"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Source {
  content: string;
  source: string;
  filename?: string;
  score?: number;
  type?: string;
}

interface Conversation {
  conversation_id: string;
  title: string;
  last_active: number;
  messages: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  followups?: string[];
  questionType?: string;
  typeDescription?: string;
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

export default function Home() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 加载会话列表
  const loadConversations = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/chat/conversations`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations || []);
      }
    } catch {
      // 后端不可达时静默
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // 新建对话
  const newConversation = () => {
    setMessages([]);
    setConversationId("");
    setError("");
    setExpandedSources({});
  };

  // 切换会话（回显历史）
  const switchConversation = async (cid: string) => {
    if (loading) return;
    abortRef.current?.abort();
    setLoading(false);
    try {
      const res = await fetch(`${API_URL}/chat/${cid}/history`);
      if (res.ok) {
        const data = await res.json();
        const history = (data.messages || []).map((m: { role: string; content: string }) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.content,
        }));
        setMessages(history);
      }
    } catch {
      // 历史加载失败：清空
      setMessages([]);
    }
    setConversationId(cid);
    setError("");
  };

  // 删除会话
  const deleteConversation = async (cid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${API_URL}/chat/${cid}`, { method: "DELETE" });
      setConversations((prev) => prev.filter((c) => c.conversation_id !== cid));
      if (cid === conversationId) newConversation();
    } catch {
      // 删除失败静默
    }
  };

  // 重命名会话
  const renameConversation = async (cid: string) => {
    const title = window.prompt("重命名会话：");
    if (!title || !title.trim()) return;
    try {
      await fetch(`${API_URL}/chat/${cid}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim() }),
      });
      loadConversations();
    } catch {
      // 重命名失败静默
    }
  };

  // 停止生成
  const stopGeneration = () => {
    abortRef.current?.abort();
  };

  const loadFollowups = async (questionText: string, answer: string, msgIndex: number) => {
    try {
      const res = await fetch(`${API_URL}/chat/followups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: questionText, answer }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.followups && data.followups.length > 0) {
          setMessages((prev) => {
            const updated = [...prev];
            if (updated[msgIndex]) {
              updated[msgIndex] = { ...updated[msgIndex], followups: data.followups };
            }
            return updated;
          });
        }
      }
    } catch {
      // followups 失败不影响主流程
    }
  };

  const ask = (text: string) => {
    setQuestion(text);
    // 触发输入后自动提交
    setTimeout(() => document.getElementById("send-btn")?.click(), 50);
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!question.trim() || loading) return;

    const userMsg = question.trim();
    setQuestion("");
    setError("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMsg },
    ]);
    setLoading(true);

    const assistantIdx = messages.length + 1;
    const controller = new AbortController();
    abortRef.current = controller;

    // 读取设置（top_k / 背景文献开关 / 检索模式）
    const topK = parseInt(localStorage.getItem("rag_top_k") || "5", 10) || 5;
    const includeBg = localStorage.getItem("rag_include_background") === "1";
    const retrievalMode = localStorage.getItem("rag_retrieval_mode") || "hybrid";

    try {
      const res = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: userMsg,
          conversation_id: conversationId,
          top_k: topK,
          include_background: includeBg,
          retrieval_mode: retrievalMode,
        }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let fullAnswer = "";
      let lastEvent = "";

      const updateAnswer = (content: string) => {
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIdx]) {
            updated[assistantIdx] = { ...updated[assistantIdx], content };
          } else {
            updated.push({ role: "assistant", content });
          }
          return updated;
        });
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // SSE 规范允许 \r\n 或 \n 行分隔（实机抓包发现浏览器收到 CRLF）
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            lastEvent = line.slice(7);
            continue;
          }
          if (!line.startsWith("data: ")) continue;

          const data = line.slice(6);

          if (lastEvent === "meta") {
            try {
              const json = JSON.parse(data);
              setMessages((prev) => {
                const updated = [...prev];
                if (!updated[assistantIdx]) {
                  updated.push({
                    role: "assistant",
                    content: "",
                    questionType: json.question_type,
                    typeDescription: json.description,
                  });
                } else {
                  updated[assistantIdx] = {
                    ...updated[assistantIdx],
                    questionType: json.question_type,
                    typeDescription: json.description,
                  };
                }
                return updated;
              });
            } catch {
              // 忽略
            }
          } else if (lastEvent === "sources") {
            try {
              const json = JSON.parse(data);
              if (Array.isArray(json)) {
                setMessages((prev) => {
                  const updated = [...prev];
                  if (!updated[assistantIdx]) {
                    updated.push({ role: "assistant", content: "", sources: json as Source[] });
                  } else {
                    updated[assistantIdx] = { ...updated[assistantIdx], sources: json as Source[] };
                  }
                  return updated;
                });
              }
            } catch {
              // 解析失败忽略
            }
          } else if (lastEvent === "token") {
            // 纯文本 token，直接追加（数字 token 如 "5" 不能被 JSON.parse 吞掉）
            fullAnswer += data;
            updateAnswer(fullAnswer);
          } else if (lastEvent === "done") {
            try {
              const json = JSON.parse(data);
              if (json && typeof json === "object" && json.conversation_id) {
                setConversationId(json.conversation_id);
              }
            } catch {
              // done 解析失败忽略
            }
          } else if (lastEvent === "error") {
            fullAnswer += `\n\n❌ ${data}`;
            updateAnswer(fullAnswer);
          }
        }
      }

      // 回答完成：刷新会话列表 + 生成建议问题
      loadConversations();
      if (fullAnswer.trim()) {
        loadFollowups(userMsg, fullAnswer, assistantIdx);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIdx]) {
            updated[assistantIdx] = {
              ...updated[assistantIdx],
              content: (updated[assistantIdx].content || "") + "\n\n_⏹ 已停止生成_",
            };
          }
          return updated;
        });
      } else {
        setMessages((prev) => {
          const updated = [...prev];
          updated[assistantIdx] = {
            role: "assistant",
            content: `❌ 出错了：${err instanceof Error ? err.message : "未知错误"}`,
          };
          return updated;
        });
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  const toggleSource = (idx: number) => {
    setExpandedSources((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <main className="app-container">
      {/* 会话侧边栏 */}
      {sidebarOpen && (
        <aside className="sidebar">
          <div className="sidebar-header">
            <button className="sidebar-btn primary" onClick={newConversation}>
              ✦ 新建对话
            </button>
          </div>
          <div className="conversation-list">
            {conversations.length === 0 && (
              <p className="sidebar-empty">暂无历史会话</p>
            )}
            {conversations.map((c) => (
              <div
                key={c.conversation_id}
                className={`conversation-item ${c.conversation_id === conversationId ? "active" : ""}`}
                onClick={() => switchConversation(c.conversation_id)}
              >
                <div className="conversation-title">{c.title || "未命名会话"}</div>
                <div className="conversation-actions">
                  <button
                    className="icon-btn"
                    title="重命名"
                    onClick={(e) => { e.stopPropagation(); renameConversation(c.conversation_id); }}
                  >
                    ✎
                  </button>
                  <button
                    className="icon-btn danger"
                    title="删除"
                    onClick={(e) => deleteConversation(c.conversation_id, e)}
                  >
                    🗑
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="sidebar-footer">
            <span className="badge">{conversations.length} 会话</span>
          </div>
        </aside>
      )}

      {/* 主聊天区 */}
      <div className="chat-area">
        <header className="header">
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title={sidebarOpen ? "收起侧边栏" : "展开侧边栏"}
          >
            {sidebarOpen ? "◀" : "▶"}
          </button>
          <div>
            <h1>🜁 神秘学顾问</h1>
            <div className="occult-divider" aria-hidden="true"><span>✦</span></div>
            <p>Occult Advisor · RAG 知识问答</p>
          </div>
          <button
            className="new-conv-btn"
            onClick={newConversation}
            disabled={loading || (messages.length === 0 && !conversationId)}
          >
            ✦ 新对话
          </button>
          <div className="nav-links">
            <a href="/alchemy" className="nav-link">🖼️ 图库</a>
            <a href="/tarot" className="nav-link">🔮 塔罗</a>
            <a href="/astro" className="nav-link">🔯 择时</a>
            <a href="/kb" className="nav-link">📚 知识库</a>
            <a href="/settings" className="nav-link">⚙️ 设置</a>
          </div>
        </header>

        <div className="messages" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="empty-state">
              <div className="icon">🜁</div>
              <div className="title">向神秘学顾问提问</div>
              <div className="subtitle">基于炼金术、塔罗、卡巴拉、占星学等 102 本知识库</div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`message-row ${msg.role}`}>
              <div className={`message-bubble ${msg.role}`}>
                {msg.role === "assistant" ? (
                  <>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>

                    {/* 检索策略 badge（Phase 4 可视化） */}
                    {msg.questionType && (
                      <div className="retrieval-meta">
                        <span className={`retrieval-type-badge ${msg.questionType}`}>
                          {msg.questionType === "overview" ? "🔭 概览检索" :
                           msg.questionType === "detail" ? "🔍 细节检索" : "🌐 通用检索"}
                        </span>
                        <span className="retrieval-desc">{msg.typeDescription}</span>
                      </div>
                    )}

                    {/* 来源引用卡片（默认折叠，点击展开） */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="sources">
                        <p
                          className="sources-label"
                          onClick={() => toggleSource(i)}
                          style={{ cursor: "pointer" }}
                        >
                          {expandedSources[i] ? "▾ 收起检索详情" : "🔍 查看检索详情（点击展开）"}
                        </p>
                        {expandedSources[i] && (
                          <>
                            {msg.sources.map((s, j) => (
                              <div key={j} className="source-card" title={s.content}>
                                <div className="source-line">
                                  <span className="source-name">
                                    {s.filename || s.source?.split("\\").pop() || "未知来源"}
                                  </span>
                                  <span className="source-type">
                                    {s.type ? (TYPE_LABEL[s.type] || s.type) : ""}
                                  </span>
                                  {typeof s.score === "number" ? (
                                    <span className="source-score">
                                      相似度 {(1 - s.score).toFixed(3)}
                                    </span>
                                  ) : (
                                    <span className="source-score bm25-tag">BM25 命中</span>
                                  )}
                                </div>
                                <div className="score-bar">
                                  <div
                                    className="score-fill"
                                    style={{ width: `${typeof s.score === "number" ? Math.max(0, Math.min(100, (1 - s.score) * 100)) : 100}%` }}
                                  />
                                </div>
                                <p className="source-content">{s.content.slice(0, 160)}...</p>
                              </div>
                            ))}
                          </>
                        )}
                      </div>
                    )}

                    {/* 建议问题 chips */}
                    {msg.followups && msg.followups.length > 0 && (
                      <div className="followups">
                        {msg.followups.map((f, j) => (
                          <button
                            key={j}
                            className="followup-chip"
                            onClick={() => ask(f)}
                            disabled={loading}
                          >
                            {f} →
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row assistant">
              <div className="message-bubble assistant">
                <span className="loading-dots">
                  <span /><span /><span />
                </span>
              </div>
            </div>
          )}
        </div>

        <form className="input-form" onSubmit={handleSubmit}>
          <div className="input-row">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="输入你的问题，如「炼金术的核心原理是什么？」"
              disabled={loading}
            />
            {loading ? (
              <button type="button" className="stop-btn" onClick={stopGeneration}>
                ⏹ 停止
              </button>
            ) : (
              <button id="send-btn" type="submit" disabled={!question.trim()}>
                发送
              </button>
            )}
          </div>
        </form>
      </div>
    </main>
  );
}
