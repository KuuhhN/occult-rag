# 🜁 神秘学顾问 · Occult RAG

基于 **RAG（Retrieval-Augmented Generation）** 的神秘学知识问答系统——把经典著作知识库变成可对话的 AI 顾问，还内置了基于知识库检索的 **塔罗占卜** 互动。

**技术栈：** FastAPI · LangChain · PostgreSQL/pgvector · Ollama · Next.js 15
**版本：** v0.4.2

> ⚠️ **开发状态：持续迭代中的个人项目**
> 知识库目前为**半成品**——已收录炼金术/塔罗/卡巴拉基础/占星等 84+ 本精排版，
> 但**卡巴拉进阶、维卡（Wicca）、符号学**等方向资料仍待补全（受限于 OCR 免费额度，
> 资料由作者逐批整理入库）。代码与架构已稳定，欢迎体验与反馈，资料会持续扩充。

---

## ✨ 功能亮点

| 功能 | 说明 | 技术点 |
|------|------|--------|
| 🧠 **RAG 知识问答** | 自然语言提问，回答带来源引用 | LangChain + pgvector + SSE 流式 |
| 🔀 **混合检索** | 向量语义 + BM25 关键词 + RRF 融合 | Postgres tsvector + nomic-embed-text |
| 🎯 **分层检索** | 按问题类型（概览/细节）分层召回 | 元数据过滤 + 关键词启发式分类 |
| 🔮 **塔罗抽牌** | 78 张牌，AI 基于知识库解读（不硬编码） | RAG 业务闭环 + 3D 翻牌动画 |
| ⚗️ **炼金图像解读** | 364 张炼金图像，VLM 解读 + 文献互证 + 附图问答 | **多模态 RAG**：pymupdf 抠图 → 智谱 glm-4v-flash 解读 → 向量化检索 |
| 💬 **多轮对话** | 会话管理、历史回显、建议问题 | Redis-free 内存记忆（最近 6 轮） |
| 📚 **知识库管理** | 统计、文档列表、上传入库、检索可视化 | /kb 管理页 + /settings 参数面板 |

---

## 🏗️ 架构

```
前端（Next.js 15）
  ├─ /         聊天页（RAG 问答 + 附图问答）
  ├─ /alchemy  炼金图像库（364 图，VLM 解读弹层）
  ├─ /tarot    塔罗抽牌（3D 翻牌）
  ├─ /kb       知识库管理
  └─ /settings 检索参数
后端（FastAPI）
  ├─ /chat           RAG 问答（SSE 流式）
  ├─ /alchemy        炼金图像（列表/详情/附图解读/搜索）
  ├─ /tarot          塔罗抽牌（RAG 解读）
  └─ /static/alchemy 炼金图静态服务
数据层
  ├─ PostgreSQL + pgvector  向量检索（langchain_pg_embedding）
  ├─ Postgres tsvector      BM25 关键词检索
  └─ Ollama                 nomic-embed-text（768 维向量）+ qwen2.5（生成）
```

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

### 3. 导入知识库（可选，无资料也能体验塔罗）

```bash
pip install -r backend/requirements.txt
python scripts/import_notes.py <你的知识库目录>
# 无知识库也能跑：塔罗功能使用内置 78 张牌数据，开箱可用；
# 知识问答需要导入资料（RAG 的知识来自知识库，作者持续补充中）
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

> **⭐ 彩蛋声明**：本仓库包含 **JOJO 的奇妙冒险 第三季（星尘斗士）塔罗牌原画**
> 22 张大阿卡纳（来自 jojowiki.com 粉丝维基），作为本项目特色彩蛋展示。
> **版权归原作者（荒木飞吕彦/集英社）所有**，本项目仅用于**个人学习、技术演示与非商业展示**，未获任何授权。
> 若您是版权方并认为本项目使用不当，请通过 GitHub Issues 联系，我们将立即移除相关图片。
> 作者深爱这部作品——这是献给 JOJO 的小小致敬。

- **JOJO 大阿卡纳**（22 张，彩蛋）：`frontend/public/images/tarot/major/`，
  来源 jojowiki.com，下载脚本 `scripts/fetch_jojo_tarot.py`
- **小阿卡纳**（56 张）：Rider-Waite 1909 **公版**（public domain），
  `scripts/fetch_tarot_assets.py` 可一键下载
- **可替换**：覆盖 `major/major-XX.jpg` 为任意图（文件名不变前端零改动）；
  不希望包含 JOJO 图的部署可删除 `major/` 目录（自动回退文字牌面）

---

## ⚗️ 炼金图像解读（多模态 RAG）

炼金术图像是理解贤者之石秘密的重要途径——本项目把炼金术书籍中的图像变成了**可检索、可对话的知识**：

- **364 张炼金图像**：从《Real Alchemy》《Manly Hall 炼金术手稿合集》《炼金术》3 本书用 pymupdf 自动抠图
- **VLM 解读**：智谱 `glm-4v-flash`（免费）逐图生成解读——图意、符号含义（衔尾蛇/凤凰/哲学家之蛋）、炼金阶段（黑化 nigredo → 白化 albedo → 红化 rubedo）
- **图像可检索（真正的多模态 RAG）**：解读文本向量化入 pgvector——问「贤者之石符号」「黑化阶段」能**检索到图像**，而不只是文字
- **附图问答**：聊天区可引用任意炼金图提问，AI 结合图像解读 + 知识库文献综合回答
- **图像管线可复现**：`scripts/extract_alchemy_images.py`（抠图）→ `compress_alchemy_images.py`（压缩 694MB→35MB）→ `interpret_alchemy_images.py`（VLM 解读，断点续跑）

> ⚠️ 炼金图像解读走**视觉模型**（智谱免费额度），**不消耗腾讯云 OCR**——OCR 只用于扫描书文字提取。

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
