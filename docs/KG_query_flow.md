# 肺炎症状查询：知识图谱 & LLM 数据流与逻辑详解 📚

本文以用户提问“肺炎有什么症状”为示例，逐步说明数据在前端、后端、知识图谱（Neo4j）与检索/生成模块之间的流动，以及每一步的具体逻辑与对应代码位置。文档重点解释：**实体抽取 → 调用 KG 搜索 → 构建 `kg_context` → 证据检索 → 构建 Prompt → LLM 调用/流式返回**。

---

## 一、总体流程（概览） 🔁

```text
用户（浏览器）
  ↓ (输入/点击“发送”)
前端 UI (`ChatView.vue`)
  ↓ 构建请求 + history（最多 12 条）
前端 store (`frontend/src/stores/chat.js`)（本地存储 & 可选同步到后端 sessions/{user_id}）
  ↓ POST /stream or POST / (QueryRequest)
后端 API (`backend/app/api/v1/endpoints/query.py`)
  ↓ 调用
QA 服务 (`backend/app/services/qa_service.py`)
  ├─ 实体抽取: `_extract_entities_from_kg` -> `_extract_entities` （识别到 "肺炎"）
  │    ↓
  │  用户记忆检索（可选）: `memory_service.search_memory(query, user_id)` → 把高相关记忆片段加入上下文
  │    ↓
  │  调用 KG 搜索（优先全文索引 `kg_fulltext` → 回退到 `CONTAINS`）：`kg_service.search_disease` / `search_symptom`
  │    ↓
  │  若匹配 -> `find_paths_for_query` -> `get_full_disease_info`（并行获取症状/用药/检查等）
  │    ↓
  │  取症状数据: `get_disease_symptoms` (Cypher via Neo4j driver)
  │    ↓
  │  构建 `kg_context` (`get_kg_context_for_query`，包含记忆检索 & 文献证据片段) & `kg_paths`（每条 path 含 `source` 与 `confidence`）
  ├─ 证据检索: `vector_service.search_documents`（文献） + `memory_service` 检索结果（可并入 evidence_context）
  ├─ 构建 Prompt: `_build_llm_prompt` / `_build_llm_prompt_without_kg`（插入 `kg_context`、`evidence_context` 与 history），并指示模型优先依据 KG 回答
  ├─ 调用 LLM 或模板（mock/gemini/openai/siliconflow）
  ↓
返回结果
  ↓ (stream 则逐块 SSE 发回；非 stream 直接返回完整 `QueryResponse`)
前端 接收流/完整响应，展示在 Chat UI（并保存至 localStorage & 可同步至后端）
```

### 流程图（Mermaid）

```mermaid
flowchart LR
  U[用户（浏览器）] --> F[前端 UI<br/>ChatView + Store]
  F --> API[后端 API<br/>POST /query 或 /query/stream]
  API --> QA[QA 服务<br/>qa_service]

  subgraph KG_Flow [知识检索与增强]
    QA --> Extract[实体抽取<br/>_extract_entities_from_kg]
    Extract --> MemorySearch[记忆检索<br/>memory_service.search_memory]
    MemorySearch --> KGSearch[KG 搜索（优先全文索引 kg_fulltext）]
    KGSearch --> FindPaths[find_paths_for_query/<br/>get_full_disease_info]
    FindPaths --> KGContext[构建 kg_context & kg_paths<br/>(含 source & confidence)]
    end

  QA --> VectorSearch[文献检索<br/>vector_service.search_documents]

  KGContext --> Prompt[构建 Prompt（包含 history / kg_context / evidence_context）]
  VectorSearch --> Prompt
  Prompt --> LLM[LLM 调用或模板<br/>(mock/gemini/openai/siliconflow)]
  LLM --> Response[响应（SSE 流或最终 QueryResponse）]
  Response --> F

  %% 性能注释
  subgraph Perf [性能优化]
    idx[全文索引（kg_fulltext）]
    mem[记忆预检（memory）]
    parallel[并行查询 + 信号量限流]
    fast[流式输出 & 前端增量渲染]
  end
  idx --> KGSearch
  mem --> MemorySearch
  parallel --> QA
  fast --> F

  classDef note fill:#f9f9f9,stroke:#ddd,color:#333;
  class Perf note;
```

---

## 二、前端（发送请求与历史） 🧭

- 位置：`frontend/src/stores/chat.js`
- 逻辑：
  - 用户点击发送后，`sendMessage(query)` 会把用户消息追加到当前会话，并构建 `historyMessages`：
    - 过滤掉 `isLoading` / `isError` 的消息
    - 保留最近 12 条（`.slice(-12)`），并映射成 `{ role, content }`
  - 调用后端接口（流式 `POST /stream` 或 普通 `POST /`），请求体为 `QueryRequest`：包含 `query`, `history`, `include_kg_paths`, `include_evidence`, `user_id` 等。
  - 本地会话会保存到 localStorage；若 localStorage 中存在 `medical_chat_user_id`（user_id），`saveToStorage()` 会自动同步当前会话到后端 `POST /api/v1/sessions`，实现跨设备会话持久化。
- 目的：把短期会话当作上下文发给后端，帮助 LLM 解析代词与多轮语境，同时支持可选的跨设备会话同步（user_id）。

示例代码片段：

```js
// frontend/src/stores/chat.js
// 使用 session 变量代替直接引用 currentSession.value
const session = sessions.value.find(s => s.id === currentSessionId.value)
const historyMessages = session.messages
  .filter(m => !m.isLoading && !m.isError)
  .slice(-12)
  .map(m => ({ role: m.role, content: m.content }))

queryAPI.streamQuery({ query, history: historyMessages, ... })
```

---

## 三、实体抽取（如何识别“肺炎”） 🧠

- 位置：`backend/app/services/qa_service.py`
- 关键函数：`_extract_entities_from_kg(query)`、`_extract_entities(query)`

逻辑详解：

1. 静态词表匹配（`_extract_entities`）：先使用内置医疗术语列表（常见疾病、症状、药物等）进行快速匹配，成本低且覆盖常见表达。
2. KG 增强匹配：若 `kg_service.is_connected` 为真，则用正则提取候选短词（`re.findall(r'[\u4e00-\u9fa5]{2,6}', query)`），对每个候选词调用：
   - `kg_service.search_disease(term, limit=1)`
   - 如果未命中，再调用 `kg_service.search_symptom(term, limit=1)`
   - 将命中的 KG 实体（标准化名称）加入实体集合
3. 去重并返回实体列表（供后续 KG 检索）。

为何混合策略：静态表保证速度，KG 检索补足词表的覆盖不足（同义词/简称/变体）。

示意代码片段：

```python
basic_entities = self._extract_entities(query)
potential_terms = re.findall(r'[\u4e00-\u9fa5]{2,6}', query)
for term in potential_terms:
    diseases = await kg_service.search_disease(term, limit=1)
    if diseases:
        found_entities.append(diseases[0])
```

---

## 四、KG 搜索（模糊搜索与精确信息） 🔎

- 位置：`backend/app/services/kg_service.py`
- 核心函数：`search_disease`, `search_symptom`, `get_full_disease_info`, `get_disease_symptoms`

细节：

1. `search_disease(keyword, limit)` / `search_symptom(keyword, limit)`：
   - 优先使用 Neo4j 的**全文索引**（fulltext index），例如管理员在 Neo4j 中创建 `kg_fulltext`，后端调用 `CALL db.index.fulltext.queryNodes(...)` 返回带 `score` 的匹配结果并按得分排序；若全文索引不可用或查询失败，回退到 `CONTAINS` 查询保证兼容性。

```cypher
# 全文索引查询（示例）
CALL db.index.fulltext.queryNodes("kg_fulltext", $query) YIELD node, score
WHERE 'Disease' IN labels(node)
RETURN node.name AS name, score
ORDER BY score DESC
LIMIT $limit
```

```cypher
# 回退示例（文本包含匹配，注意 alias 存在性判断）
MATCH (d:Disease)
WHERE d.name CONTAINS $keyword OR (d.alias IS NOT NULL AND any(a IN d.alias WHERE a CONTAINS $keyword))
RETURN d.name as name
LIMIT $limit
```

- 返回名字列表（字符串），用于模糊匹配与实体标准化（例如把“肺炎”匹配为图谱中的标准节点名）。

- 说明：较新版本 Neo4j 不再支持 `exists(node.prop)` 语法；应使用 `node.prop IS NOT NULL` 判断属性存在/非空。

2. `get_disease_info(name)` 与 `get_full_disease_info(name)`：

   - `get_disease_info`：按名查询疾病节点的属性（简介、病因、预防等）。
   - `get_full_disease_info`：在确认疾病名后并行调用多个查询（症状、用药、饮食、检查、科室、并发症等），使用 `asyncio.gather` 提高性能，合并为完整字典返回。

3. `get_disease_symptoms(disease_name)`：获取该疾病的症状列表，示例 Cypher：

```cypher
MATCH (d:Disease {name: $name})-[:has_symptom]->(s:Symptom)
RETURN s.name as symptom
```

---

## 五、构建 `kg_context` 与 `kg_paths`（结构化到文本/路径） 🧩

- 位置：`kg_service.py` 的 `get_kg_context_for_query` 与 `find_paths_for_query`

逻辑：

1. `find_paths_for_query(entities)`：为可视化返回结构化路径（`KGPath`、`KGNode`、`KGEdge`）

   - 对前 N 个实体（例如最多 5 个）：
     - 若实体能作为疾病获得 `get_full_disease_info` 的结果，则构建以疾病为中心的路径：疾病节点 + 若干症状/药物节点 + 边，并设置 `relevance_score`、`source`（例如 `neo4j`/`memory`）与 `confidence`（0-1）。
     - 否则当作症状，查找相关疾病并构建症状 → 疾病的路径，同时标注来源与置信度。
   - 返回供前端展示的路径列表（最多 5 条），前端 `EvidencePanel` 会显示每条路径的来源与置信度，便于判断证据强弱。
   - 若字段较长，做截断以避免过多 token。返回最终 `kg_context` 字符串。

示例 `kg_context`：

```
【肺炎】
简介：肺炎是肺实质感染导致……
症状：咳嗽、发热、咳痰、呼吸困难、胸痛
检查项目：胸片、血常规、痰培养
```

---

## 六、证据检索（向量/文献检索） 🔬

- 位置：`backend/app/services/vector_service.py`
- 关键函数：`search_documents(query, keywords=None, limit=5)`

当前实现（Mock 模式）逻辑：

1. 服务支持 Qdrant（真实向量库）或 `_mock_mode`（样例文献）。当前默认 `mock` 模式。
2. Mock 匹配：基于 `query` 与 `keywords`（来自实体）做字符串/关键词匹配与简单打分，返回 top-N 文档作为 `Evidence`，包含 `source`, `snippet`, `pmid/doi/url`, `confidence` 等。
3. 如果连接真实向量库，应基于 query embedding 做相似度检索，返回最相关文献片段。

QA 层会把前若干 `evidence` 聚合成 `evidence_context` 字符串供 LLM 参考或直接放入 `QueryResponse.evidence` 给前端展示。

---

## 七、构建 Prompt（把 KG、证据、历史合并） ✍️

- 位置：`qa_service.py` 中的 `_build_history_context`, `_build_llm_prompt`, `_build_llm_prompt_without_kg`

逻辑：

1. 历史处理：

   - 前端发送最近 12 条消息，后端拼接时只取最后 6 条（`for msg in request.history[-6:]`）以避免 token 爆炸。
   - `_build_history_context` 将历史消息转为文本块（"用户：...\n 助手：...\n"），插入 Prompt，帮助 LLM 理解代词和上下文。

2. KG 与证据优先级：

   - 当 `kg_context` 非空时，使用带有“**优先使用知识图谱信息**”约束的 prompt 模板（`_build_llm_prompt`），并把 `kg_context` 与 `evidence_context` 一并插入。
   - 当无 KG 时，使用 `_build_llm_prompt_without_kg`，并在生成后追加 `no_kg_notice`（注明为 LLM 来源）。

3. 消息序列（chat API）：
   - 如果使用 Chat API（OpenAI/Gemini/SiliconFlow），构造 `messages = [system] + history_messages + [user prompt]`，把历史作为 prior messages 插入，这比把历史直接拼成 prompt 更符合对话接口的范式。

示例（简化）片段：

```python
messages = [{"role": "system", "content": system_content}]
messages.extend(history_messages)
messages.append({"role": "user", "content": prompt})
```

---

## 八、LLM 调用与流式返回（整体控制） 🧩

- 位置：`qa_service.process_query` 与 `process_query_stream`

关键点：

1. 并发与超时控制：

   - 使用 `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` 限制并发（防止 LLM 调用耗光资源）
   - 对外部 LLM 调用使用 `asyncio.wait_for(..., timeout=LLM_TIMEOUT)` 做超时处理

2. 多种提供者：支持 `mock`, `gemini`, `openai`, `siliconflow`；不同 provider 在调用细节上不同（Gemini SDK 为同步，使用 `run_in_executor`；OpenAI/SiliconFlow 支持流式 `stream=True`）。

3. 流式输出：
   - `process_query_stream` 会先 `yield` 检索状态（e.g., searching / evidence_found），随后在生成阶段逐块 `yield` 生成内容（SSE 格式），最后 `yield` 完整 `QueryResponse`（序列化）。
   - 前端在接收流时累积文本并更新 UI（`isStreaming`、`isLoading` 标志）。

---

## 九、降级与错误处理 ⚠️

- 若 Neo4j 未连接，`kg_service.is_connected` 为 False：
  - `search_*`、`get_full_disease_info` 等返回空或默认值；QA 层会在 `warnings` 标记 `知识图谱服务未连接`，并降级为仅使用向量检索或 LLM 模板回答。
- 若 LLM 调用超时或出错：
  - 使用 `_generate_mock_response` 或 `_generate_fallback_response` 作为回退，确保用户获得可读回复而非 500 错误。

---

## 十、为什么模型回复更快（性能改进总结） 🚀

下面是导致你观察到「大模型回复变快」的主要原因，以及每项优化所在的代码位置和作用：

- **Neo4j 全文索引（`kg_fulltext`）优先检索**

  - 位置：`backend/app/services/kg_service.py`（`search_disease` / `search_symptom`）
  - 说明：全文索引通过 `CALL db.index.fulltext.queryNodes(...)` 按 score 返回结果，速度比 `CONTAINS` 更快且更精准，减少了模糊匹配耗时和后续额外检索次数。

- **用户记忆（Memory）检索提前补充上下文**

  - 位置：`backend/app/services/memory_service.py` 与 `backend/app/services/qa_service.py`（集成点）
  - 说明：在去调用 LLM 之前先检索高相关记忆片段并把它们加入 `kg_context`/`evidence_context`，很多问题可直接由记忆或 KG 回答，减少 LLM 生成长度与频次。

- **并行与限流（异步并发与信号量）**

  - 位置：`backend/app/services/qa_service.py`（`asyncio.gather()` 与 `asyncio.Semaphore`）
  - 说明：并行获取 KG 的多项数据（症状/药物/检查等）减少等待时间；信号量避免单个慢调用阻塞其他请求，提高总体吞吐。

- **完善的降级与模板回答**

  - 位置：`qa_service.py`（`_generate_mock_response`、fallback 逻辑）
  - 说明：当 KG 可用且能直接回答时使用模板化回答或简短生成，避免调用大型模型进行长文本生成，显著减少响应时长。

- **流式输出与前端增量渲染**

  - 位置：`backend/app/services/qa_service.py`（`process_query_stream`）与 `frontend/src/services/api.js`（stream 解析）
  - 说明：SSE 流式发送搜证/生成状态与内容片段，前端增量展示用户感知延迟更小（感觉更快）。

- **向量/证据服务优化（Mock 或向量库）**

  - 位置：`backend/app/services/vector_service.py`（mock 优化或 Qdrant 检索）
  - 说明：证据检索结果数量限制及高效检索减少了供 LLM 参考的上下文体积，从而缩短生成时间。

- **前端截断与会话尺寸控制**
  - 位置：`frontend/src/stores/chat.js`（只发送最近 12 条，后端取最后 6 条）
  - 说明：减少传输与 prompt 大小，避免超长上下文导致更长的模型处理时间。

这些协同优化使得在多数查询中，系统可以通过本地检索（KG / memory / evidence）快速构建高质量上下文并在可能的情况下跳过或缩短 LLM 的完整生成，从而显著降低用户感知的等待时间。

---

## 十一、参考代码位置（一览） 📁

- 前端：`frontend/src/stores/chat.js`（构建 `history`、流式处理、可选的会话同步）
- 后端 API：`backend/app/api/v1/endpoints/query.py`
- QA 逻辑：`backend/app/services/qa_service.py`（已集成用户记忆检索）
- 知识图谱服务：`backend/app/services/kg_service.py`（已支持全文索引优先检索）
- 向量/证据服务：`backend/app/services/vector_service.py`
- 记忆服务：`backend/app/services/memory_service.py`（SQLite 持久 + 简单相似度检索）
- 会话服务：`backend/app/services/session_service.py`（跨设备会话持久化）
- 模型/数据模型：`backend/app/models/query.py`（`KGPath` 已新增 `source` 和 `confidence` 字段`）

---
