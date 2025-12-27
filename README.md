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

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3 + Vite)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Chat UI     │  │  KG Viewer   │  │  Evidence Panel      │   │
│  │  (实时对话)   │  │  (Cytoscape) │  │  (来源引用)          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI + Python)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Query API   │  │  RAG Engine  │  │  Auth & Audit        │   │
│  │  (/api/v1)   │  │  (LLM+检索)  │  │  (JWT + 日志)        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│    Neo4j         │ │   Qdrant     │ │   PostgreSQL     │
│  (知识图谱)       │ │  (向量索引)  │ │  (元数据/审计)    │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

## 📁 项目结构

```
.
├── backend/                 # FastAPI 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── utils/          # 工具函数
│   ├── data/               # 示例数据
│   ├── tests/              # 测试用例
│   └── requirements.txt
├── frontend/               # Vue 3 前端应用
│   ├── src/
│   │   ├── components/     # Vue 组件
│   │   ├── views/          # 页面视图
│   │   ├── stores/         # Pinia 状态管理
│   │   └── services/       # API 服务
│   └── package.json
├── diseasekg/              # 知识图谱构建脚本
└── docs/                   # 文档
```

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
