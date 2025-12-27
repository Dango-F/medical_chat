# 基于知识图谱的医疗问答系统 (Medical KG QA System)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-green.svg)](https://vuejs.org/)

一个基于知识图谱和大语言模型的医疗问答系统，支持自然语言问答、证据级参考、可视化知识浏览与分析报表。

## 🌟 功能特性

- **自然语言问答**: 用户可用自然语言提问医疗相关问题（症状、疾病、用药、指南解释等）
- **混合检索**: 知识图谱 + 向量检索的混合检索策略
- **证据溯源**: 所有回答均有来源引用（PubMed、临床指南、DrugBank 等）
- **知识图谱可视化**: 交互式节点/边浏览，支持路径高亮
- **置信度评分**: 显示可信度分数与医疗免责声明
- **响应式设计**: 支持桌面端和移动端，暗黑模式

## 🏗️ 技术架构

概览：系统采用前后端分离模式，后端以 FastAPI 提供结构化问答 API 与流式 SSE（Server-Sent Events），并通过混合检索（KG + 向量检索）结合 LLM 生成高质量、可溯源的医疗回答。

主要组件：

- 前端（Vue 3 + Vite）

  - Chat UI：主对话交互，支持流式显示、消息历史、撤回/重发等操作
  - KG Viewer：基于 Cytoscape 的知识图谱可视化（路径高亮、节点详情）
  - Evidence Panel：展示证据列表、文献片段、置信度与来源链接

- 后端（FastAPI + Python）

  - API/Router：暴露标准 REST 与流式接口（/api/v1/query, /api/v1/query/stream）
  - QAService（RAG 引擎）：负责实体抽取、KG 检索、向量检索、构建 LLM prompt 与 LLM 调用（支持 OpenAI / Gemini / SiliconFlow）
  - KG Service（Neo4j）：知识图谱查询与上下文构建（支持全文索引 `kg_fulltext`）
  - Vector Service（Qdrant 或 Mock）：文献/文档检索（用于证据检索）
  - Memory Service（SQLite）：短期持久记忆（按 user_id 存储问答摘录并检索）
  - Session Service（持久会话）：会话同步与跨设备恢复
  - Logging & Audit：日志（loguru）、审计记录与可选 DB 存储

- 数据存储
  - Neo4j：知识图谱主存储（Disease / Symptom / Drug / ...）
  - Qdrant（可选）：向量索引（文献/证据检索）
  - SQLite / PostgreSQL：记忆、会话或审计（按部署需要）

关键特性与实现要点：

- 混合检索（RAG）：先用 KG 做实体消解与上下文，再用向量检索补充文献证据，最终把 KG 内容 + 证据片段注入 LLM prompt（或在 KG-only 模式下使用模板化回答）。
- 流式输出：使用 SSE 将检索和生成状态逐步推送到前端，改善用户感知延迟。
- 可配置 LLM：根据 env（`.env`）选择 OpenAI / Gemini / SiliconFlow，平台中实现超时保护、线程池封装（阻塞 SDK）等兼容层。
- 可观测性：详细 debug 日志会记录实体抽取、证据检索的中间结果，有利于问题定位（参见 `docs/DEBUG.md`）。

（更多实现细节可参见 `docs/KG_query_flow.md` 与 `docs/DEBUG.md`）

---

### 架构图（可视化）

下面使用 Mermaid 格式展示系统架构（GitHub 支持 Mermaid）：

```mermaid
flowchart TB
  subgraph FE [Frontend (Vue 3 + Vite)]
    ChatUI["Chat UI<br>(实时对话)"]
    KGViewer["KG Viewer<br>(Cytoscape)"]
    Evidence["Evidence Panel<br>(证据显示)"]
  end

  subgraph BE [Backend (FastAPI + Python)]
    API["Query API<br>(/api/v1 & SSE)"]
    RAG["RAG Engine<br>(实体抽取 + KG + Vector + LLM)"]
    Auth["Auth & Audit<br>(JWT + 日志)"]
  end

  ChatUI -->|HTTP / SSE| API
  KGViewer -->|API| API
  Evidence -->|API| API
  API --> RAG
  RAG --> Neo4j["Neo4j<br>(知识图谱)"]
  RAG --> Qdrant["Qdrant<br>(向量索引)"]
  API --> Postgres["PostgreSQL<br>(元数据/审计)"]

  style FE fill:#f3f4f6,stroke:#9ca3af
  style BE fill:#fef3c7,stroke:#f59e0b
  style Neo4j fill:#a7f3d0,stroke:#10b981
  style Qdrant fill:#bfdbfe,stroke:#3b82f6
  style Postgres fill:#fbcfe8,stroke:#ec4899
```

> 注：如果 README 在某些渲染环境不显示 Mermaid，你也可以参考上方的 ASCII 图（兼容性更好）。

## 📁 项目结构

```
.
├── backend/                 # FastAPI 后端服务
│   ├── app/
│   │   ├── api/            # API 路由（/api/v1）
│   │   ├── core/           # 核心配置（settings, logging）
│   │   ├── models/         # Pydantic 数据模型（QueryRequest/QueryResponse 等）
│   │   ├── services/       # 业务实现（qa_service, kg_service, vector_service, memory_service, session_service）
│   │   └── utils/          # 工具函数与中间件
│   ├── data/               # 示例与测试数据
│   ├── tests/              # 单元/集成测试
│   └── requirements.txt
├── frontend/               # Vue 3 + Vite 前端应用
│   ├── src/
│   │   ├── components/     # 可复用组件（ChatMessage, EvidencePanel, SettingsModal）
│   │   ├── views/          # 页面视图（ChatView, GraphView, HomeView）
│   │   ├── stores/         # Pinia 状态管理（sessions, chat store）
│   │   └── services/       # 前端 API 客户端（queryAPI, sessionAPI）
│   ├── public/
│   └── package.json
├── diseasekg/              # 知识图谱构建脚本（medical.json -> Neo4j）
│   ├── data/               # 源数据（medical.json）
│   ├── dict/               # 词典与辅助文件
│   └── prepare_data/       # 抓取与清洗脚本
├── docs/                   # 文档（DEBUG.md, KG_query_flow.md, BUILD.md 等）
├── .gitignore
└── README.md
```

提示：更多关于 KG 构建流程与调试信息请参见 `docs/KG_query_flow.md` 与 `docs/DEBUG.md`。

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Neo4j 5.x

### 快速开始

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp env.example.txt .env
# 编辑 .env 文件配置 API Key 和数据库连接

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 📖 API 文档

启动后端服务后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 核心接口

#### POST /api/v1/query - 问答查询

```json
// 请求
{
  "query": "头痛两天，可能是什么原因？",
  "max_answers": 3,
  "include_kg_paths": true
}

// 响应
{
  "answer": "头痛可能由多种原因引起...",
  "evidence": [
    {
      "source": "PubMed",
      "snippet": "偏头痛是一种常见的原发性头痛...",
      "pmid": "12345678",
      "confidence": 0.93,
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678"
    }
  ],
  "kg_paths": [...],
  "warnings": ["本系统仅供参考，不能替代医生诊断"],
  "confidence_score": 0.89
}
```

## ⚠️ 免责声明

**重要提示**: 本系统为医疗信息检索及参考工具，**不能替代专业医生的诊断和治疗建议**。

- 所有临床建议仅供参考，需经专业医疗人员核实
- 紧急情况请立即就医或拨打急救电话
- 系统不存储或处理个人健康信息 (PHI)
- 使用本系统即表示您已理解并接受以上声明

## 📊 数据来源

本系统知识图谱数据来源于以下公开医学资源：

| 数据源          | 类型     | 许可证         |
| --------------- | -------- | -------------- |
| PubMed/MEDLINE  | 文献摘要 | Public Domain  |
| DrugBank (Open) | 药物数据 | CC BY-NC 4.0   |
| ICD-10          | 疾病编码 | WHO License    |
| 临床指南        | 诊疗规范 | 各发布机构许可 |

## 🧪 测试

```bash
# 后端测试
cd backend
pytest tests/ -v --cov=app

# 前端测试
cd frontend
npm run test
```

## 📝 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议。请查看 [CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## 📞 联系方式

如有问题或建议，请通过 Issues 提交。
