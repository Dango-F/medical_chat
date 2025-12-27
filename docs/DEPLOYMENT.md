# 部署指南 - 医疗知识问答系统

本文档提供完整的部署说明。

## 目录

- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [本地开发](#本地开发)
- [生产环境配置](#生产环境配置)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

---

## 环境要求

### 最低配置

| 组件    | 版本要求 |
| ------- | -------- |
| Python  | 3.11+    |
| Node.js | 18+      |
| Neo4j   | 5.x      |

### 推荐硬件配置

| 环境 | CPU   | 内存  | 存储       |
| ---- | ----- | ----- | ---------- |
| 开发 | 2 核  | 8GB   | 20GB       |
| 生产 | 4 核+ | 16GB+ | 100GB+ SSD |

---

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd medical_chat
```

### 2. 启动 Neo4j

确保 Neo4j 数据库已启动运行：

```bash
# 如果使用 Neo4j Desktop，直接启动数据库
# 或者使用命令行启动（需要先安装 Neo4j）
neo4j start
```

### 3. 启动后端

```powershell
cd backend

# 创建并激活虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制并编辑 .env 文件）
copy env.example.txt .env
# 编辑 .env 文件配置 API Key 等

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 启动前端

```powershell
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 访问服务

| 服务          | URL                        | 说明           |
| ------------- | -------------------------- | -------------- |
| 前端应用      | http://localhost:5173      | Vue 3 Web 界面 |
| 后端 API      | http://localhost:8000      | FastAPI 服务   |
| API 文档      | http://localhost:8000/docs | Swagger UI     |
| Neo4j Browser | http://localhost:7474      | 知识图谱可视化 |

---

## 本地开发

### 后端开发

```powershell
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
# 复制 env.example.txt 为 .env 并编辑

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```powershell
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

### 运行测试

```powershell
# 后端测试
cd backend
pytest tests/ -v --cov=app

# 特定测试
pytest tests/test_api.py -v

# 前端测试
cd frontend
npm run test
```

---

## 生产环境配置

### 1. 环境变量

创建 `.env` 文件：

````bash
# Application
APP_NAME="Medical KG QA System"
APP_ENV=production
DEBUG=false
SECRET_KEY=your-super-secret-key-here

# LLM 配置（选择其一）
LLM_PROVIDER=siliconflow

# SiliconFlow (推荐)
SILICONFLOW_API_KEY=sk-your-key
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3

# 或使用 OpenAI
# OPENAI_API_KEY=sk-your-production-key

# 或使用 Gemini
# GEMINI_API_KEY=your-gemini-key

# Neo4j

## 建议：为 KG 启用全文索引（可提高模糊匹配与同义词检索）

建议在 Neo4j 控制台执行下列 Cypher（示例为创建名为 `kg_fulltext` 的全文索引，覆盖 `Disease` 与 `Symptom` 节点的 `name`、`alias`、`description` 字段）：

```cypher
CALL db.index.fulltext.createNodeIndex("kg_fulltext", ["Disease","Symptom"], ["name","alias","description"])
````

创建后可以用下面的查询测试效果：

```cypher
CALL db.index.fulltext.queryNodes("kg_fulltext", "肺炎") YIELD node, score
RETURN node.name AS name, score
LIMIT 10
```

如果 Neo4j 未启用或索引缺失，服务会自动回退到原始 `CONTAINS` 查询以保证兼容性。
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=strong-password-here

# Qdrant (可选)

QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=medical_docs

# CORS (生产环境限制域名)

CORS_ORIGINS=["https://your-domain.com"]

# Logging

LOG_LEVEL=WARNING

````

### 2. 生产环境启动

```powershell
# 后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端构建
cd frontend
npm run build
# 使用任意静态文件服务器托管 dist 目录
````

---

## 配置说明

### 后端配置项

| 配置项              | 默认值                | 说明                 |
| ------------------- | --------------------- | -------------------- |
| APP_ENV             | development           | 运行环境             |
| DEBUG               | true                  | 调试模式             |
| SECRET_KEY          | -                     | JWT 密钥             |
| LLM_PROVIDER        | siliconflow           | LLM 提供商           |
| SILICONFLOW_API_KEY | -                     | SiliconFlow API 密钥 |
| OPENAI_API_KEY      | -                     | OpenAI API 密钥      |
| GEMINI_API_KEY      | -                     | Gemini API 密钥      |
| NEO4J_URI           | bolt://localhost:7687 | Neo4j 连接地址       |
| NEO4J_USER          | neo4j                 | Neo4j 用户名         |
| NEO4J_PASSWORD      | password              | Neo4j 密码           |
| QDRANT_HOST         | localhost             | Qdrant 主机          |
| QDRANT_PORT         | 6333                  | Qdrant 端口          |
| LOG_LEVEL           | INFO                  | 日志级别             |

### 前端配置项

| 配置项       | 默认值 | 说明         |
| ------------ | ------ | ------------ |
| VITE_API_URL | /api   | API 基础路径 |

---

## 常见问题

### Q: 启动后无法连接 Neo4j？

A: 检查 Neo4j 服务是否正常启动，确保 Neo4j 完全启动后再启动后端。

### Q: 前端显示 API 错误？

A: 确保后端服务正常运行并且 CORS 配置正确。检查浏览器控制台的详细错误信息。

### Q: 如何使用自己的 API Key？

A: 在 `.env` 文件中配置：

```bash
# SiliconFlow（推荐，国内可用）
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=sk-your-key

# 或 OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key

# 或 Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key
```

### Q: Mock 模式和真实模式有什么区别？

A: 不配置 LLM API Key 时，系统使用 Mock 模式：

- 使用预设的回答模板
- 不调用真实的 LLM
- 适合演示和开发测试

### Q: 如何扩展知识图谱数据？

A: 可以通过以下方式：

1. 修改 `backend/app/services/kg_service.py` 中的 Mock 数据
2. 直接在 Neo4j Browser 中导入数据
3. 使用 Neo4j 的 Cypher 语句批量导入
4. 使用 `diseasekg/` 目录下的脚本构建知识图谱

---

## 技术支持

如遇到问题，请：

1. 查看后端日志输出
2. 检查 `.env` 配置是否正确
3. 查看 [docs/DEBUG.md 中的常见问题](./DEBUG.md#常见问题)
4. 提交 Issue 并附上相关日志信息
