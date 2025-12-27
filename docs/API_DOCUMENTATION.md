# API 文档 - 医疗知识问答系统

## 概述

本文档描述了医疗知识问答系统的 REST API 接口。所有 API 都遵循 RESTful 设计原则。

**Base URL**: `http://localhost:8000/api/v1`

## 认证

当前 MVP 版本不需要认证。生产环境将支持：

- OAuth2 + JWT
- API Key

## API 端点

### 1. 问答接口

#### POST /query - 提交查询

提交医疗问题并获取基于知识图谱的回答。

**请求体**:

```json
{
  "query": "头痛两天了，可能是什么原因？",
  "user_id": "user_123", // 可选
  "context": "无其他症状", // 可选，上下文信息
  "max_answers": 3, // 可选，默认3，范围1-10
  "include_kg_paths": true, // 可选，默认true
  "include_evidence": true, // 可选，默认true
  "language": "zh" // 可选，默认"zh"
}
```

**响应** (200 OK):

```json
{
  "query_id": "q_abc123def456",
  "answer": "## 头痛的可能原因分析\n\n根据您描述的症状...",
  "evidence": [
    {
      "source": "中华神经科杂志",
      "source_type": "pubmed",
      "snippet": "偏头痛是一种常见的原发性头痛...",
      "pmid": "34567890",
      "doi": null,
      "url": "https://pubmed.ncbi.nlm.nih.gov/34567890",
      "confidence": 0.95,
      "publication_date": "2023",
      "section": "偏头痛的诊断与治疗进展"
    }
  ],
  "kg_paths": [
    {
      "nodes": [
        { "id": "S001", "label": "头痛", "type": "Symptom", "properties": {} },
        { "id": "D001", "label": "偏头痛", "type": "Disease", "properties": {} }
      ],
      "edges": [
        {
          "source": "D001",
          "target": "S001",
          "type": "HAS_SYMPTOM",
          "properties": {}
        }
      ],
      "relevance_score": 0.85
    }
  ],
  "confidence_score": 0.89,
  "warnings": [],
  "disclaimer": "⚠️ 重要提示：本系统仅供医疗信息参考...",
  "processing_time_ms": 1234,
  "model_used": "gpt-4"
}
```

**错误响应**:

- `422 Validation Error`: 请求参数验证失败
- `500 Internal Server Error`: 服务器内部错误

---

#### GET /query/examples - 获取示例问题

获取预设的示例问题列表。

**响应** (200 OK):

```json
{
  "examples": [
    {
      "id": 1,
      "query": "头痛两天了，可能是什么原因？",
      "category": "症状咨询"
    }
  ],
  "total": 10
}
```

---

### 2. 知识图谱接口

#### GET /kg/node/{node_id} - 获取节点详情

获取指定节点及其邻居节点信息。

**参数**:

- `node_id` (path): 节点 ID，如 "D001", "S001"

**响应** (200 OK):

```json
{
  "node": {
    "id": "D001",
    "label": "偏头痛",
    "type": "Disease",
    "properties": {
      "icd10": "G43",
      "description": "一种常见的原发性头痛..."
    },
    "description": "一种常见的原发性头痛...",
    "aliases": [],
    "external_ids": {}
  },
  "neighbors": [
    {
      "node": {
        "id": "S001",
        "label": "头痛",
        "type": "Symptom",
        "properties": {}
      },
      "relationship_type": "HAS_SYMPTOM",
      "relationship_direction": "outgoing",
      "relationship_properties": { "frequency": "常见" }
    }
  ],
  "total_neighbors": 5
}
```

**错误响应**:

- `404 Not Found`: 节点不存在

---

#### GET /kg/search - 搜索节点

按关键词搜索知识图谱节点。

**查询参数**:

- `q` (required): 搜索关键词
- `types` (optional): 节点类型过滤，逗号分隔，如 "Disease,Drug"
- `limit` (optional): 返回数量限制，默认 20，范围 1-100

**响应** (200 OK):

```json
{
  "nodes": [
    {
      "id": "D001",
      "label": "偏头痛",
      "type": "Disease",
      "properties": {...},
      "description": "..."
    }
  ],
  "total": 1,
  "query": "头痛"
}
```

---

#### GET /kg/graph - 获取图谱数据

获取用于可视化的图谱数据。

**查询参数**:

- `limit` (optional): 节点数量限制，默认 100，范围 1-500

**响应** (200 OK):

```json
{
  "nodes": [
    {
      "id": "D001",
      "label": "偏头痛",
      "type": "Disease",
      "properties": {...}
    }
  ],
  "edges": [
    {
      "source": "D001",
      "target": "S001",
      "type": "HAS_SYMPTOM",
      "properties": {...}
    }
  ]
}
```

---

#### GET /kg/stats - 获取统计信息

获取知识图谱的统计数据。

**响应** (200 OK):

```json
{
  "total_nodes": 50,
  "total_relationships": 100,
  "node_types": {
    "Disease": 10,
    "Symptom": 15,
    "Drug": 8,
    "Guideline": 5,
    "Reference": 10,
    "WarningSign": 2
  },
  "relationship_types": {
    "HAS_SYMPTOM": 30,
    "TREATS": 25,
    "COVERS": 10
  }
}
```

---

#### GET /kg/types - 获取节点类型

获取所有节点类型定义。

**响应** (200 OK):

```json
{
  "types": [
    {
      "id": "Disease",
      "label": "疾病",
      "color": "#ef4444",
      "description": "疾病实体，如偏头痛、糖尿病"
    }
  ]
}
```

---

### 3. 反馈接口

#### POST /feedback - 提交反馈

提交用户对回答质量的反馈。

**请求体**:

```json
{
  "query_id": "q_abc123",
  "feedback_type": "helpful", // helpful, not_helpful, incorrect, missing_info, other
  "rating": 5, // 可选，1-5
  "comment": "回答很准确", // 可选
  "user_id": "user_123", // 可选
  "suggested_answer": "..." // 可选，建议的正确答案
}
```

**响应** (200 OK):

```json
{
  "feedback_id": "fb_xyz789",
  "status": "received",
  "message": "感谢您的反馈！",
  "created_at": "2024-01-01T12:00:00Z"
}
```

---

#### GET /feedback/stats - 反馈统计

获取反馈统计数据（管理员接口）。

**响应** (200 OK):

```json
{
  "total": 100,
  "by_type": {
    "helpful": 80,
    "not_helpful": 10,
    "incorrect": 5,
    "missing_info": 5
  },
  "average_rating": 4.2
}
```

---

## 数据模型

### Evidence (证据)

| 字段             | 类型    | 描述                                                |
| ---------------- | ------- | --------------------------------------------------- |
| source           | string  | 来源名称                                            |
| source_type      | enum    | pubmed, guideline, drugbank, knowledge_graph, other |
| snippet          | string  | 证据摘要片段                                        |
| pmid             | string? | PubMed ID                                           |
| doi              | string? | DOI                                                 |
| url              | string? | 来源链接                                            |
| confidence       | float   | 置信度 (0-1)                                        |
| publication_date | string? | 发布日期                                            |
| section          | string? | 章节/标题                                           |

### KGNode (知识图谱节点)

| 字段       | 类型   | 描述     |
| ---------- | ------ | -------- |
| id         | string | 节点 ID  |
| label      | string | 节点标签 |
| type       | string | 节点类型 |
| properties | object | 节点属性 |

### KGPath (知识图谱路径)

| 字段            | 类型     | 描述         |
| --------------- | -------- | ------------ |
| nodes           | KGNode[] | 路径中的节点 |
| edges           | KGEdge[] | 路径中的边   |
| relevance_score | float    | 相关性分数   |

---

## 错误处理

所有错误响应遵循以下格式：

```json
{
  "detail": "错误描述信息"
}
```

### HTTP 状态码

| 状态码 | 描述           |
| ------ | -------------- |
| 200    | 成功           |
| 400    | 请求参数错误   |
| 404    | 资源不存在     |
| 422    | 验证错误       |
| 500    | 服务器内部错误 |

---

## 速率限制

当前 MVP 版本无速率限制。生产环境建议：

- 普通用户: 60 请求/分钟
- 认证用户: 300 请求/分钟

---

## 示例代码

### Python

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# 发送查询
response = requests.post(f"{BASE_URL}/query", json={
    "query": "头痛可能是什么原因？",
    "max_answers": 3
})

data = response.json()
print(f"回答: {data['answer']}")
print(f"置信度: {data['confidence_score']}")
for ev in data['evidence']:
    print(f"  - {ev['source']}: {ev['snippet'][:50]}...")
```

### JavaScript

```javascript
const response = await fetch("http://localhost:8000/api/v1/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "头痛可能是什么原因？",
    max_answers: 3,
  }),
});

const data = await response.json();
console.log("回答:", data.answer);
console.log("证据数量:", data.evidence.length);
```

### cURL

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "头痛可能是什么原因？", "max_answers": 3}'
```
