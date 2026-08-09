# 🜁 神秘学顾问 · Occult RAG

基于 **RAG（Retrieval-Augmented Generation）** 的神秘学知识问答系统——把经典著作知识库变成可对话的 AI 顾问，还内置了基于知识库检索的 **塔罗占卜** 互动。

**技术栈：** FastAPI · LangChain · PostgreSQL/pgvector · Ollama · Next.js 15
**版本：** v0.4.2

---

## ✨ 功能亮点

| 功能 | 说明 | 技术点 |
|------|------|--------|
| 🧠 **RAG 知识问答** | 自然语言提问，回答带来源引用 | LangChain + pgvector + SSE 流式 |
| 🔀 **混合检索** | 向量语义 + BM25 关键词 + RRF 融合 | Postgres tsvector + nomic-embed-text |
| 🎯 **分层检索** | 按问题类型（概览/细节）分层召回 | 元数据过滤 + 关键词启发式分类 |
| 🔮 **塔罗抽牌** | 78 张牌，AI 基于知识库解读（不硬编码） | RAG 业务闭环 + 3D 翻牌动画 |
| 💬 **多轮对话** | 会话管理、历史回显、建议问题 | Redis-free 内存记忆（最近 6 轮） |
| 📚 **知识库管理** | 统计、文档列表、上传入库、检索可视化 | /kb 管理页 + /settings 参数面板 |

---

## 🏗️ 架构

```
浏览器 (Next.js 15)
      │  SSE 流式
      ▼
FastAPI ──► 问题分类（overview/detail）──► 检索层
      │                                      ├── 向量检索（pgvector 余弦距离）
      │                                      └── BM25 关键词（Postgres tsvector）
      │                                      └── RRF 融合排序
      ▼
LangChain + Ollama（qwen2.5:7b）──► 带来源引用的回答
      ▲
PostgreSQL/pgvector（文档块 + 向量 + JSONB 元数据）
```

**混合检索（hybrid retrieval）**：稠密向量擅长语义相似，BM25 擅长专有名词精确匹配（塔罗牌名/咒语名/人名），用 RRF（Reciprocal Rank Fusion，`score = Σ 1/(k+rank)`，k=60）无需归一化直接融合排序——面试可深挖的设计。

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装 Ollama（macOS/Linux/Windows: https://ollama.com/download）
ollama pull nomic-embed-text    # embedding 模型（768 维）
ollama pull qwen2.5:7b          # 对话模型（中文效果好）
```

### 2. 启动后端 + 数据库

```bash
docker compose up -d db
docker compose up backend
# 健康检查：http://localhost:8000/health
```

### 3. 导入知识库（可选，自带示例数据）

```bash
pip install -r backend/requirements.txt
python scripts/import_notes.py <你的知识库目录>
# 无知识库也能跑（塔罗功能使用内置 78 张牌数据）
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 **http://localhost:3000** — 开始提问或抽牌。

---

## 📚 目录结构

```
occult-rag/
├── docker-compose.yml          # PostgreSQL + pgvector
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI 入口（lifespan 自动迁移）
│   │   ├── config.py           # 环境变量配置
│   │   ├── data/tarot_cards.py # 78 张塔罗牌标准数据
│   │   ├── rag/
│   │   │   ├── ingest.py       # 入库（分块→向量化→tsvector 触发器）
│   │   │   ├── retrieve.py     # 分层检索（overview/detail/general）
│   │   │   ├── hybrid.py       # 混合检索（BM25 + 向量 + RRF）
│   │   │   └── memory.py       # 会话记忆
│   │   └── routes/
│   │       ├── chat.py         # 问答 API（SSE 流式）
│   │       ├── kb.py           # 知识库管理
│   │       └── tarot.py        # 塔罗抽牌（RAG 解读）
│   └── tests/                  # 24 个 pytest 测试
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # 聊天主界面
│   │   ├── tarot/              # 塔罗抽牌页（3D 翻牌）
│   │   ├── kb/                 # 知识库管理页
│   │   └── settings/           # 检索参数设置页
│   └── public/images/tarot/    # 牌面图（不入库，见版权说明）
├── scripts/                    # 导入/验证脚本
└── README.md
```

---

## 🔮 塔罗抽牌（特色功能）

- **78 张标准牌**（22 大阿卡纳 + 56 小阿卡纳，RWS 体系）
- **牌意不硬编码**：每张牌用牌名构造检索 query → 从知识库（如《塔罗冥想》）检索 → LLM 基于检索内容生成解读——真实 RAG 业务形态
- **3D 互动**：牌背朝上 → 点击翻牌 → 解读淡入 → 综合解读（三张牌阵）
- **卡背分级**：大阿卡纳紫色 JOJO 风格卡背、小阿卡纳金色符文卡背

### 牌面图版权

牌面图**不提交 Git 仓库**（`.gitignore` 排除）：
- **默认**：Rider-Waite 1909 公版（public domain），`scripts/fetch_tarot_assets.py` 可一键下载 78 张
- **可替换**：`frontend/public/images/tarot/major/major-XX.jpg` 覆盖为任意图（如 JOJO 第三季原画），文件名不变则前端零改动
- **注意**：动漫/商业美术（如《JOJO 的奇妙冒险》）请勿提交公开仓库（侵权风险），本地演示可自行替换

---

## 📖 面试 FAQ（项目设计问答）

**Q: 为什么用混合检索（向量 + BM25）？**
A: 纯向量检索对语义相似有效，但专有名词/精确术语（塔罗牌名、咒语名、人名）召回弱。BM25 关键词检索补充精确匹配，RRF 融合两者排序。

**Q: RRF 为什么不需要归一化？**
A: RRF 用排名而非分数：`score = Σ 1/(k + rank)`。两个检索器打分尺度不同（余弦距离 vs ts_rank），排名融合天然免疫尺度差异，k=60 是标准值。

**Q: 分层检索解决什么问题？**
A: "这本书讲了什么"（概览）应该命中笔记/导读层（浓缩精华），"仪式具体步骤"（细节）应该命中精排版/原文层（信息全）。按问题类型过滤元数据，避免概览问题被碎片段落污染。

**Q: 中文场景 BM25 的局限？**
A: Postgres 'simple' 分词按空格/标点切分，中文连续文本不分词——BM25 中文召回有限。这正是向量检索兜底的原因（互补而非替代）。

**Q: 塔罗解读为什么不硬编码？**
A: 解读内容随知识库变化——从《塔罗冥想》检索的解读和从《金色黎明》检索的不同，体现"知识库即数据源"的 RAG 设计；且新书入库后解读自动进化。

---

## 📡 API

启动后端后访问 `http://localhost:8000/docs`（Swagger UI）。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/chat/stream` | POST | RAG 问答（SSE 流式 + 来源引用 + 建议问题） |
| `/chat` | POST | RAG 问答（非流式，多轮） |
| `/chat/conversations` | GET | 会话列表 |
| `/tarot/draw` | POST | 塔罗抽牌（牌面 + RAG 解读 + 综合解读 + 来源） |
| `/kb/stats` | GET | 知识库统计（块数/类型分布） |
| `/kb/documents` | GET | 文档列表 |
| `/health` | GET | 健康检查 |

---

## 🔧 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/occult_rag` | PG 连接串 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 地址 |
| `EMBEDDING_MODEL` | `nomic-embed-text` | 向量化模型 |
| `LLM_MODEL` | `qwen2.5:7b` | 对话模型 |
| `DATA_ROOT` | `/app/data` | 目录导入允许的根目录 |

---

## ⚠️ 安全说明（部署前必读）

当前版本面向**本地单用户**。公开部署前必须处理：

| 风险 | 修复方案 |
|------|---------|
| 全站无认证 | 加 API Key/登录；`uvicorn --host 127.0.0.1` |
| 会话 IDOR | 服务端生成会话 ID 并绑定身份 |
| 弱默认凭据（postgres:postgres） | 环境变量注入强口令 |
| Prompt 注入（已缓解） | history/context 已标记不可信 + 定界符 |

已内置防护：目录导入限制在 `DATA_ROOT` 内、上传 10MB 上限、错误信息脱敏、SQL 全参数化、SSE 事件不可伪造。

---

## 📜 License

MIT — 见 [LICENSE](LICENSE)。
