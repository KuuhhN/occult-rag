# 🜁 神秘学顾问 · Occult RAG

基于 RAG（Retrieval-Augmented Generation）的神秘学知识问答系统。

**技术栈：** FastAPI + LangChain + PostgreSQL/pgvector + Ollama + Next.js 15
**版本：** v0.2.0（多轮对话）

---

## 是什么

把你的 occult-ingest 知识库（133 篇笔记、27 本神秘学经典）变成**可对话的 AI 顾问**。

用户用自然语言提问（如「炼金术的核心原理是什么？」），系统自动从知识库检索相关内容，由本地大模型生成带来源引用的回答。

---

## 架构

```
浏览器 (Next.js Chat UI)
       │
       ▼
FastAPI 后端 ──▶ LangChain RAG Pipeline
       │              │
       │         ┌────▼──────────┐
       │         │ Ollama        │
       │         │ embedding     │
       │         │ + qwen2.5:7b  │
       │         └───────────────┘
       │
       ▼
PostgreSQL + pgvector
  └── 文档块 + 向量 + 元数据
```

---

## 快速开始

### 1. 环境准备

```bash
# 安装 Ollama
# macOS/Linux: curl -fsSL https://ollama.com/install.sh | sh
# Windows: https://ollama.com/download

# 拉取模型
ollama pull nomic-embed-text    # embedding 模型 (768维)
ollama pull qwen2.5:7b           # 对话模型（中文效果好，~4GB）
```

### 2. 启动服务

```bash
cd occult-rag

# 启动 PostgreSQL + 后端
docker compose up -d db
docker compose up backend
```

### 3. 导入知识库

```bash
# 将 occult-ingest 笔记向量化入库
# 假设 occult-ingest 在同级目录
pip install -r backend/requirements.txt
python scripts/import_notes.py ../occult-ingest/knowledge-base
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:3000 — 开始向神秘学顾问提问。

---

## API 文档

启动后端后访问 http://localhost:8000/docs 查看 Swagger UI。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/chat` | POST | RAG 问答（非流式，多轮对话） |
| `/chat/stream` | POST | RAG 问答（SSE 流式，多轮对话） |
| `/chat/conversations` | GET | 会话列表（调试用） |
| `/chat/{conversation_id}` | DELETE | 清空会话历史 |
| `/ingest/file` | POST | 上传 .md 文件入库 |
| `/ingest/directory` | POST | 批量导入目录 |
| `/health` | GET | 健康检查 |

### 多轮对话

请求体带 `conversation_id` 即可延续上下文（后端保留最近 6 轮）：

```bash
# 第一问（自动生成会话 ID）
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是贤者之石？"}'
# → {"answer": "...", "conversation_id": "abc123"}

# 追问（带上会话 ID，AI 能理解上下文）
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "它和点金石是一回事吗？", "conversation_id": "abc123"}'
```

### 示例请求

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "炼金术的七大操作是什么？"}'
```

---

## 项目结构

```
occult-rag/
├── docker-compose.yml        # PostgreSQL + pgvector
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 环境变量配置
│   │   ├── database.py       # 同步引擎 + 连接检测
│   │   ├── rag/
│   │   │   ├── ingest.py     # 文档入库（分块→向量化→存储）
│   │   │   ├── retrieve.py   # 语义检索
│   │   │   └── chain.py      # LangChain RAG 问答链
│   │   ├── routes/
│   │   │   ├── chat.py       # 聊天 API
│   │   │   └── ingest.py     # 入库 API
│   │   └── models/
│   │       └── schemas.py    # Pydantic 模型
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # 聊天主界面
│   │   ├── layout.tsx        # 根布局
│   │   └── globals.css       # 暗色主题样式
│   └── package.json
├── scripts/
│   └── import_notes.py       # 批量导入笔记
└── README.md
```

---

## 与 occult-ingest 的关系

| 维度 | occult-ingest | occult-rag |
|------|--------------|------------|
| 定位 | PDF → 笔记 管线 | 笔记 → 问答 服务 |
| 存储 | Markdown + Obsidian | PostgreSQL + pgvector |
| 查询 | 人手动翻 | AI 语义检索 |
| 输出 | 静态笔记 | 流式对话 + 来源引用 |
| 用户 | 个人学习 | 多用户 Web 服务 |

occult-ingest 是**上游**（把书变成笔记），occult-rag 是**下游**（让 AI 基于笔记回答任何问题）。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/occult_rag` | PG 连接串 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 地址 |
| `EMBEDDING_MODEL` | `nomic-embed-text` | 向量化模型 |
| `LLM_MODEL` | `qwen2.5:7b` | 对话模型 |
| `DATA_ROOT` | `/app/data` | 目录导入允许的根目录 |

## 安全说明（部署前必读）

当前版本面向**本地单用户**使用。公开部署前必须处理：

| 风险 | 说明 | 修复方案 |
|------|------|---------|
| 全站无认证 | 所有端点开放，8000 端口暴露所有网卡 | 加 API Key/登录；`uvicorn --host 127.0.0.1` |
| 会话 IDOR | conversation_id 客户端可指定，无用户绑定 | 服务端生成会话 ID 并绑定身份 |
| 弱默认凭据 | PostgreSQL 口令 `postgres:postgres` | 环境变量注入强口令 |
| Prompt 注入（已缓解） | history/context 已标记不可信并加定界符 | 本地 7B 模型下足够；高安全场景改用消息级隔离 |

已内置的防护：目录导入限制在 `DATA_ROOT` 内（防路径穿越）、上传 10MB 上限、错误信息脱敏（不泄露内部异常）、SQL 全参数化、SSE 事件不可伪造。

---

## 简历亮点

这个项目覆盖了以下岗位要求：

- ✅ **AI 智能体 & 自动化工作流**：LangChain RAG Pipeline
- ✅ **PostgreSQL + 数据打标签**：pgvector 向量存储 + JSONB 元数据
- ✅ **接口 & API**：FastAPI + SSE 流式响应
- ✅ **RAG 向量知识库**：从零搭建语义检索系统
- ✅ **文档标准化**：完整 README + API 文档
- ✅ **前后端分离**：Next.js + FastAPI 架构

---

## License

MIT — 与 occult-ingest 保持一致。

## 🎴 塔罗牌面版权（v0.4.1）

塔罗抽牌页使用 78 张牌面图，**图片不提交 Git 仓库**（见 `.gitignore`）：

- **当前牌面**：Rider-Waite 1909 公版牌面（public domain），
  下载脚本 `scripts/fetch_tarot_assets.py`（源：GitHub lalesleon13-hash/Tarot）
- **大阿卡纳可替换**：`frontend/public/images/tarot/major/major-XX.jpg`
  可覆盖为任意图（如 JOJO 第三季立绘），文件名不变则前端零改动
- **版权说明**：若替换为动漫/商业美术（如《JOJO 的奇妙冒险》原画），
  请勿将图片提交至公开仓库（侵权风险）——本仓库只保留占位图与公版牌面，
  本地演示可自行替换
- 命名映射表见 `scripts/tarot_assets.md`
