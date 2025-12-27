# 调试问题记录

本文档记录项目开发过程中遇到的问题及其解决方案。

---

## 目录 📚

- 问题与修复

  - 问题 1： [多窗口并发查询时响应缓慢或无响应](#problem-1)
  - 问题 2： [Pydantic 字段命名冲突警告](#problem-2)
  - 问题 3： [Gemini SDK 同步调用阻塞事件循环](#problem-3)
  - 问题 4： [多轮对话上下文丢失](#problem-4)
  - 问题 5： [知识图谱实体提取不准确](#problem-5)
  - 问题 6： [知识图谱无数据时的回答策略](#problem-6)
  - 问题 7： [流式输出调试与优化](#problem-7)

- [性能优化与建议](#perf)
- [常用调试命令](#common-commands)
- [新增功能与使用说明（重要）](#new-features)
- [日志查看与架构说明](#logs)
- [实现细节与调试要点（详述）](#implementation-details)

> 注：本目录为快速导航参考。

---

<a id="problem-1"></a>

## 问题 1：多窗口并发查询时响应缓慢或无响应

### 问题描述

- **现象**：当用户同时打开多个浏览器窗口进行问答查询时，所有请求都没有响应或响应极慢
- **单窗口时**：正常响应
- **多窗口时**：请求排队，长时间无响应

### 问题分析

1. **Uvicorn 单 Worker 模式**

   - 开发环境使用 `uvicorn app.main:app --reload` 启动
   - 默认只有一个 worker 进程
   - 无法真正并行处理多个请求

2. **LLM API 调用阻塞**

   - 调用 SiliconFlow/DeepSeek-V3 API 需要 5-30 秒
   - 一个请求在处理时，其他请求全部排队等待
   - 没有超时控制，可能无限期阻塞

3. **无并发限制**
   - 没有限制同时处理的请求数量
   - 可能导致资源耗尽

### 解决方案

#### 1. 添加并发控制信号量

在 `backend/app/services/qa_service.py` 中：

```python
class QAService:
    # 并发控制：限制同时处理的请求数
    MAX_CONCURRENT_REQUESTS = 5
    # LLM 调用超时时间（秒）
    LLM_TIMEOUT = 60

    def __init__(self):
        # ...
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def process_query(self, request: QueryRequest) -> QueryResponse:
        # 使用信号量控制并发
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async with self._semaphore:
            return await self._process_query_internal(request)
```

#### 2. 添加 LLM 调用超时控制

```python
# SiliconFlow 调用添加超时
response = await asyncio.wait_for(
    self.siliconflow_client.chat.completions.create(...),
    timeout=self.LLM_TIMEOUT
)
```

### 验证方法

1. 重启后端服务
2. 打开多个浏览器窗口同时发送查询
3. 观察是否能够并行响应

---

<a id="problem-2"></a>

## 问题 2：Pydantic 字段命名冲突警告

### 问题描述

启动时出现警告：

```
UserWarning: Field "model_used" has conflict with protected namespace "model_".
```

### 问题分析

Pydantic v2 中 `model_` 前缀是保护的命名空间，用于内部方法如 `model_dump()`、`model_validate()` 等。

### 解决方案

在模型类中添加配置：

```python
from pydantic import BaseModel

class QueryResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_used: str  # 现在可以正常使用
```

或者重命名字段为 `llm_model_used`。

---

<a id="problem-3"></a>

## 问题 3：Gemini SDK 同步调用阻塞事件循环

### 问题描述

- **现象**：使用 Gemini 作为 LLM 时，整个服务在请求期间无响应
- **原因**：Gemini SDK (`google.generativeai`) 是同步的，直接调用会阻塞 asyncio 事件循环

### 问题分析

FastAPI 使用 asyncio 事件循环处理请求。如果在 async 函数中调用同步的阻塞函数，会导致整个事件循环被阻塞，所有其他请求都无法处理。

### 解决方案

使用 `loop.run_in_executor()` 将同步调用放到线程池中执行：

```python
elif self._llm_provider == "gemini":
    prompt = self._build_llm_prompt(request.query, kg_context, evidence_context, request.history)
    try:
        # Gemini SDK 是同步的，使用 run_in_executor 避免阻塞事件循环
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,  # 使用默认线程池
                lambda: self.gemini_model.generate_content(
                    f"你是一个专业、严谨的医疗信息助手。\n\n{prompt}",
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 2000,
                    }
                )
            ),
            timeout=self.LLM_TIMEOUT
        )
        answer = response.text
    except asyncio.TimeoutError:
        logger.warning(f"Gemini call timed out after {self.LLM_TIMEOUT}s, using fallback")
        answer = self._generate_mock_response(request.query, entities, evidence, kg_paths, kg_context)
```

---

<a id="problem-4"></a>

## 问题 4：多轮对话上下文丢失

### 问题描述

- **现象**：用户进行多轮对话时，AI 无法理解上下文中的代词指代
- **例如**：用户先问"糖尿病怎么治疗"，再问"它有什么并发症"，AI 无法理解"它"指的是糖尿病

### 问题分析

1. 前端没有发送对话历史
2. 后端 LLM 调用时没有包含历史消息

### 解决方案

#### 1. 定义对话历史模型

在 `backend/app/models/query.py` 中：

```python
class ChatMessage(BaseModel):
    """Chat message for conversation history"""
    role: str = Field(..., description="消息角色 (user/assistant)")
    content: str = Field(..., description="消息内容")

class QueryRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    history: Optional[List[ChatMessage]] = Field(default=None, description="对话历史")
    # ...其他字段
```

#### 2. 在 Prompt 中包含历史

```python
def _build_llm_prompt(self, query: str, kg_context: str, evidence_context: str, history: list = None) -> str:
    # 构建对话历史部分
    history_context = ""
    if history and len(history) > 0:
        history_context = "\n**对话历史**：\n"
        for msg in history[-6:]:  # 只保留最近6轮对话，避免上下文过长
            role_name = "用户" if msg.role == "user" else "助手"
            history_context += f"{role_name}：{msg.content}\n"
        history_context += "\n"

    return f"""你是一个专业的医疗信息助手...
{history_context}
**当前用户问题**：{query}
..."""
```

#### 3. 在 LLM 调用中传入历史消息

```python
# 构建完整的消息列表
messages = [
    {"role": "system", "content": "你是一个专业、严谨的医疗信息助手..."}
]
# 添加历史消息
if request.history:
    for msg in request.history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
# 添加当前问题
messages.append({"role": "user", "content": prompt})
```

#### 已修复：多轮上下文记忆与指代消解改进

- **变更位置**：`backend/app/services/qa_service.py`

- **变更概述**：将 `_extract_entities_from_kg` 扩展为接受 `history` 参数并进行三阶段增强：

  1. 对当前 query 做静态规则提取与 KG 增强检索（优先全文索引 / 回退 CONTAINS）；
  2. 若当前 query 未能提取到实体，则回溯最近用户消息（最多 6 条）并尝试在历史中检索实体，以解决代词/省略问题；
  3. 最后把历史与当前 query 合并再做一次检索作为补偿性步骤；去重并按发现顺序返回实体。

- **验证方法（示例）**：

  1. 发送：`POST /api/v1/query`，body: `{"query": "肺炎有什么症状？"}`
  2. 再发送：`POST /api/v1/query`，body: `{"query": "那应该吃什么药治疗"}`
  3. 预期结果：第二次请求能识别出“肺炎”实体并触发 KG 用药检索，回答中包含基于知识图谱的用药建议；亦可在后端日志中查看 `Extracted entities` 日志行以确认识别到的实体。

- **备注与后续改进建议**：
  - 当前使用启发式回溯方法能显著改善多数场景，但在复杂共指（跨多轮或多实体混合）场景下仍可能存在误判。
  - 后续可选方案：引入中文共指解析（coreference）模型或把历史/实体向量化并使用语义检索（Embeddings + 向量库）进行更稳健的指代解析与检索增强。

---

<a id="problem-5"></a>

## 问题 5：知识图谱实体提取不准确

### 问题描述

- **现象**：用户输入的疾病名称与知识图谱中的名称不完全匹配时，无法获取相关信息
- **例如**：用户输入"感冒"，但知识图谱中是"普通感冒"或"流行性感冒"

### 问题分析

原来只使用静态词表进行实体提取，无法覆盖知识图谱中的所有实体。

### 解决方案

在 `qa_service.py` 中添加知识图谱增强的实体提取：

```python
async def _extract_entities_from_kg(self, query: str) -> List[str]:
    """从知识图谱中提取实体（更准确）"""
    found_entities = []

    # 首先用基础规则提取
    basic_entities = self._extract_entities(query)
    found_entities.extend(basic_entities)

    # 然后尝试从知识图谱中搜索匹配
    if kg_service.is_connected:
        # 提取可能的关键词（2-6个字的词）
        potential_terms = re.findall(r'[\u4e00-\u9fa5]{2,6}', query)

        for term in potential_terms:
            if term in found_entities:
                continue
            # 尝试在知识图谱中搜索
            diseases = await kg_service.search_disease(term, limit=1)
            if diseases:
                found_entities.append(diseases[0])
            else:
                symptoms = await kg_service.search_symptom(term, limit=1)
                if symptoms:
                    found_entities.append(symptoms[0])

    return list(set(found_entities))
```

---

<a id="problem-6"></a>

## 问题 6：知识图谱无数据时的回答策略

### 问题描述

- **现象**：当用户询问的内容在知识图谱中没有收录时，需要让大模型仍能给出回答，但要明确标注来源
- **需求**：区分"基于知识图谱的回答"和"纯大模型生成的回答"

### 判断逻辑

在 `backend/app/services/qa_service.py` 中：

```python
# Step 4: 从知识图谱获取上下文
kg_context = ""
if entities and kg_service.is_connected:
    kg_context = await kg_service.get_kg_context_for_query(entities)

# 备用：如果 kg_context 为空但有路径数据，从路径构建
if not kg_context and kg_paths:
    kg_context = "相关医学知识：\n..."

# ⭐ 关键判断：知识图谱是否有数据
kg_available = bool(kg_context or kg_paths)
```

### 判断流程图

```
用户问题: "膝盖疼怎么办？"
           ↓
    1. 提取实体 → entities = ["膝盖疼"] 或 []
           ↓
    2. 查询知识图谱 → kg_paths = [...] 或 []
           ↓
    3. 获取知识图谱上下文 → kg_context = "..." 或 ""
           ↓
    4. 判断: kg_available = bool(kg_context or kg_paths)
           ↓
      ┌─────────────────┬─────────────────┐
      │  kg_available   │  kg_available   │
      │    = True       │    = False      │
      ├─────────────────┼─────────────────┤
      │ 有知识图谱数据   │ 知识图谱无数据   │
      │ 用 kg_context   │ 用纯 LLM 回答   │
      │ 喂给 LLM        │ + 追加来源标注  │
      └─────────────────┴─────────────────┘
```

### 解决方案

#### 1. 根据知识图谱可用性选择不同的 Prompt

```python
if kg_available:
    # 有知识图谱数据，使用标准 prompt
    prompt = self._build_llm_prompt(request.query, kg_context, evidence_context, request.history)
    system_content = "请根据提供的医疗知识图谱信息回答问题..."
else:
    # 无知识图谱数据，使用纯 LLM prompt
    prompt = self._build_llm_prompt_without_kg(request.query, request.history)
    system_content = "请根据你的医学专业知识回答问题..."
```

#### 2. 无知识图谱时追加来源标注

```python
# 无知识图谱数据时的来源标注
no_kg_notice = f"""

---
🤖 **来源说明**：知识图谱中未找到相关信息，本回答由 AI 大模型（{current_model_name}）基于通用医学知识生成。
⚠️ **重要提示**：AI 生成内容仅供参考，可能存在误差，请以专业医生诊断为准。
"""

# 如果无知识图谱数据，追加来源标注
if not kg_available:
    answer += no_kg_notice
```

#### 3. 在响应中标识回答来源

在 `QueryResponse` 模型中添加 `answer_source` 字段：

```python
class AnswerSource(str, Enum):
    KNOWLEDGE_GRAPH = "knowledge_graph"  # 基于知识图谱
    LLM_ONLY = "llm_only"  # 纯大模型生成（知识图谱无数据）
    MIXED = "mixed"  # 混合来源（知识图谱 + LLM）
    TEMPLATE = "template"  # 模板回复（无LLM）
```

### 判断条件汇总

| 条件                                | `kg_available` | `answer_source` | 处理方式          |
| ----------------------------------- | -------------- | --------------- | ----------------- |
| `kg_context` 有内容                 | `True`         | `mixed`         | 知识图谱 + LLM    |
| `kg_context` 空但 `kg_paths` 有数据 | `True`         | `mixed`         | 从路径构建上下文  |
| 两者都为空 + 有 LLM                 | `False`        | `llm_only`      | 纯 LLM + 来源标注 |
| 两者都为空 + 无 LLM                 | `False`        | `template`      | 模板回复          |

### 什么情况下知识图谱会没数据？

1. **用户问的内容不在知识图谱中**（如"膝盖疼"、"腰椎间盘突出"等未收录）
2. **实体提取失败**（用户问法太口语化，无法识别医学术语）
3. **Neo4j 服务未连接**（`kg_service.is_connected = False`）

<a id="perf"></a>

## 性能优化建议

### LLM 模型选择

| 模型                | 响应速度    | 质量 | 推荐场景 |
| ------------------- | ----------- | ---- | -------- |
| DeepSeek-V3         | 慢 (10-30s) | 高   | 复杂问题 |
| DeepSeek-V2.5       | 中 (5-15s)  | 中高 | 一般问答 |
| Qwen2.5-7B-Instruct | 快 (2-5s)   | 中   | 快速响应 |

### 知识图谱查询优化

1. **并行查询**：使用 `asyncio.gather()` 并行获取疾病的多个关联信息

```python
(symptoms, drugs, foods, checks, departments, cure_ways, complications) = await asyncio.gather(
    self.get_disease_symptoms(disease_name),
    self.get_disease_drugs(disease_name),
    self.get_disease_foods(disease_name),
    self.get_disease_checks(disease_name),
    self.get_disease_department(disease_name),
    self.get_disease_cure_ways(disease_name),
    self.get_disease_complications(disease_name)
)
```

2. **限制结果数量**：避免返回过多数据

3. **缓存热门查询**：对于高频查询的疾病可以添加缓存

### 其他优化

1. **添加 Redis 缓存**：缓存常见问题的回答
2. **异步流式响应**：使用 SSE 逐步返回内容
3. **请求去重**：避免用户重复提交相同问题

---

## 代码中已实现的检索加速点（与位置）

下面列出代码中已经实现的、能够显著提高知识图谱检索速度的逻辑点与对应文件位置，便于你快速核查和验证：

- **全文索引优先检索（Neo4j fulltext）**

  - 位置：`backend/app/services/kg_service.py`（`_fulltext_query_nodes`, `search_disease`, `search_symptom`）
  - 说明：优先调用 `CALL db.index.fulltext.queryNodes(...)` 按 score 返回匹配，避免 `CONTAINS` 全表扫描，性能与命中率显著提升。

- **并行查询与限制返回量**

  - 位置：`backend/app/services/kg_service.py`（`get_full_disease_info` 使用 `asyncio.gather`；`find_paths_for_query` 限制实体数量并返回 top N）
  - 说明：并行执行症状/用药/检查等子查询，减少串行等待；限制返回数量减少后续处理与传输开销。

- **记忆预检减少 LLM 调用**

  - 位置：`backend/app/services/memory_service.py` 与 `backend/app/services/qa_service.py`
  - 说明：在调用 LLM 之前检索用户记忆并把高相关记忆加入 `kg_context`，许多问题可直接由记忆或 KG 回答，避免昂贵的模型生成。

- **前端/后端共同的截断策略**

  - 位置：`frontend/src/stores/chat.js`（只发送最近 12 条历史）与 `backend/app/services/qa_service.py`（只取最近 6 条历史，`get_kg_context_for_query` 限制实体与字段长度）
  - 说明：限制传输与 prompt 大小，降低模型处理时间与 token 成本。

- **限流与超时保护**

  - 位置：`backend/app/services/qa_service.py`（`asyncio.Semaphore`, `LLM_TIMEOUT`）
  - 说明：避免少数慢调用阻塞系统，提高整体吞吐与稳定性。

- **流式返回改善用户感知延迟**
  - 位置：`backend/app/services/qa_service.py`（`process_query_stream`）与前端 SSE 解析
  - 说明：增量发送状态与内容，让用户即时看到结果片段，提高体验（感知更快）。

### 常用诊断命令（用于验证索引与查询计划）

- 查看索引列表（根据 Neo4j 版本）：

```
SHOW INDEXES;
-- 或
CALL db.indexes();
```

- 测试全文索引命中：

```cypher
CALL db.index.fulltext.queryNodes("kg_fulltext", "肺炎") YIELD node, score
RETURN node.name AS name, score
LIMIT 10;
```

- 查看查询计划与成本：

```cypher
EXPLAIN MATCH (d:Disease) WHERE d.name CONTAINS '肺炎' RETURN d.name LIMIT 10;
PROFILE MATCH (d:Disease) WHERE d.name CONTAINS '肺炎' RETURN d.name LIMIT 10;
```

### 短期建议（不改代码即可快速验证）

1. 用以上 `PROFILE` 或 `CALL db.index.fulltext.queryNodes` 测试典型查询的延迟与命中情况；
2. 对热点实体（如常见病）手动运行 `get_kg_context_for_query` 并检查耗时；
3. 如果发现某些查询仍慢，可先在运维层面（Neo4j 配置、page_cache / JVM heap）做排查，再决定是否引入 Redis 缓存或 ES 同步。

---

<a id="common-commands"></a>

## 常用调试命令

```bash
# 检查服务健康状态
curl http://localhost:8000/health

# 测试 API 响应
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "头痛怎么办？"}'

# 测试带历史的多轮对话
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "它有什么症状？",
    "history": [
      {"role": "user", "content": "糖尿病怎么治疗"},
      {"role": "assistant", "content": "糖尿病的治疗方法包括..."}
    ]
  }'

# 检查知识图谱连接状态
curl http://localhost:8000/api/v1/kg/stats

# 启动后端服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动后端服务（多 worker）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

<a id="new-features"></a>

## 新增功能与使用说明（重要）

下面列出近期新增的功能、配置与调试说明，便于验证与排查：

### 已实现改进（概要）

- 优先使用 **Neo4j 全文索引**（`kg_fulltext`）用于 `search_disease` / `search_symptom`，若索引缺失则自动回退到 `CONTAINS` 查询，提升模糊匹配、同义词和变体搜索的鲁棒性。
- 在 `KGPath` 中增加 `source` 与 `confidence` 字段（后端 `backend/app/models/query.py`），前端 `EvidencePanel` 已显示来源与置信度（百分比）以便排序与展示证据强弱。
- 新增 **memory_service**（`backend/app/services/memory_service.py`）：将问答对以短时记忆形式保存到 SQLite，并在后续查询中按相似度检索并作为查询上下文补充（仅在提供 `user_id` 时启用）。
- 新增 **session_service**（`backend/app/services/session_service.py`）与 REST API（`POST /api/v1/sessions`, `GET /api/v1/sessions/{user_id}`, 等），前端 `chat` store 会在检测到本地 `medical_chat_user_id` 时自动同步当前会话到后端，以支持跨设备访问。

---

### 最近修复与改进（2025-12-27）

下面是近期针对你反馈的问题所做的修复与改进，包含验证方法：

- 证据检索范围限定为“当前问题”（已修复）

  - 问题：当会话多轮提问时，查看某一轮回答的证据会意外包含之前轮的证据。
  - 修复：后端在检索文献证据时改为使用仅基于**当前 query** 抽取的实体（方法：`QAService._extract_entities_from_query_only`），并在流式/非流式路径同时生效。
  - 文件：`backend/app/services/qa_service.py`（已记录 debug 日志 `Extracted current-only entities for evidence`）。
  - 验证：在对话中先问“发烧...”，再问一个无关问题，然后查看第二条回答的证据，应只包含与第二个问题相关的文献。

- 同义词与口语化映射（已加）

  - 问题：像“**小儿麻痹症**”这种口语化/别名无法稳定命中 `脊髓灰质炎`。
  - 修复：在 `QAService` 中新增 `SYNONYMS` 映射（例如 `"小儿麻痹症" -> "脊髓灰质炎"`），优先把口语化词替换为规范疾病名进行后续 KG 检索和上下文构建。
  - 文件：`backend/app/services/qa_service.py`（`SYNONYMS` 与相关映射日志）。
  - 验证：发送 `小儿麻痹症是啥` 应能抽取到 `脊髓灰质炎` 并返回对应 KG 摘要。

- 疾病检索优先级与归一化（已改进）

  - 问题：查询像“普通流感”时，错误地把 `禽流感` 排在首位。
  - 修复：`kg_service.search_disease` 现在按顺序尝试：1) **精确匹配**（名称或别名相等）→ 2) **全文索引 kg_fulltext** → 3) **CONTAINS 回退**（并按相关性排序：精确 > startswith > contains），同时对常见修饰词（例如“普通/常见/季节性”）做简单归一化后重试。
  - 文件：`backend/app/services/kg_service.py`。
  - 验证：`search_disease("普通流感")` 应返回 `流感/流行性感冒` 而非 `禽流感`。

- 更激进的查询回退（处理“XX 是啥”类短问句）

  - 问题：像“普通流感/小儿麻痹症是啥”这种直接提问，有时无法被规则实体抽取命中。
  - 修复：在实体抽取中添加了对问句后缀清理（`是什么/是啥/是什么意思` 等）的回退逻辑，并尝试用清理后的整个 query 去直接做疾病搜索；还加入了基于 n-gram 的短词扫描以提高命中率。
  - 文件：`backend/app/services/qa_service.py`（`_extract_entities_from_kg` 的 fallback 扫描）。
  - 验证：对 `小儿麻痹症是啥`、`普通流感` 等问句进行测试，确认能命中预期疾病并返回 KG 摘要。

- 管理对话 UI 调整（前端）

  - 改动：把“管理对话”按钮改为占一整行的有边框按钮，位于“新对话”上方（并增强样式与说明）。
  - 文件：`frontend/src/views/ChatView.vue`。
  - 验证：打开侧栏，按钮位于顶部且占一行，点击后进入选择模式并显示“完成管理”与批量操作。

- 文档链接修复
  - 改动：修复了 `docs/DEPLOYMENT.md` 中对 `docs/DEBUG.md` 的引用为可点击链接（相对路径）。

如果你希望，我可以：

1. 将上述每一项补充到 `docs/DEBUG.md` 的不同小节（包括示例和复现命令），或
2. 只保留一条“最近修复”摘要（就像现在一样），或
3. 帮你运行逐项的本地验证脚本并把输出贴上来以便确认（需要我运行的话会执行相关后端函数以打印结果）。

---

### 1) Neo4j 全文索引（`kg_fulltext`）

### 1) Neo4j 全文索引（`kg_fulltext`）

- **作用**：提升 `search_disease` / `search_symptom` 的模糊匹配、同义词与分词鲁棒性；服务会优先尝试全文索引，若索引缺失则回退到 `CONTAINS`。
- **在 Neo4j 控制台创建索引**：

```cypher
CALL db.index.fulltext.createNodeIndex("kg_fulltext", ["Disease","Symptom"], ["name","alias","description"])
```

- **验证（Cypher）**：

```cypher
CALL db.index.fulltext.queryNodes("kg_fulltext", "肺炎") YIELD node, score
RETURN node.name AS name, score
LIMIT 10
```

- **验证（API）**：通过前端或 curl 测试搜索接口：

```
curl "http://localhost:8000/api/v1/kg/search?q=肺炎&types=Disease"
```

- **日志与回退**：若索引缺失，后端会在日志中输出 debug 信息并回退到 `CONTAINS` 查询以保证兼容性。

### 2) 用户记忆（`memory_service`）

- **功能**：在用户提供 `user_id` 时，系统会把问答摘要存为短期记忆（SQLite，文件：`data/memories.db`），并在后续查询中以相似度检索相关记忆并把它们加入 `kg_context`/`evidence_context` 作为补充上下文。
- **触发方式**：在请求体中包含 `"user_id": "<your_id>"` 即会自动写入记忆，且每次查询会尝试检索与当前 query 相似的记忆（top-k）。
- **验证**：
  1. 发送一次带 `user_id` 的查询：

```
curl -X POST http://localhost:8000/api/v1/query -H "Content-Type: application/json" -d '{"query": "我昨晚发烧并咳嗽", "user_id": "user123"}'
```

2. 再发送相关问题检查返回的流或最终响应中是否包含 `用户历史记忆` 段落或检索到的记忆内容；也可以打开 `data/memories.db` 查看是否写入。

- **位置**：`backend/app/services/memory_service.py`（实现为 SQLite + 简单相似度检索，后续可替换为 Embeddings + 向量库）。

### 3) 会话持久化（`session_service`）

- **功能**：按 `user_id` 存储会话，支持跨设备同步与恢复。后端提供 REST API：
  - `POST /api/v1/sessions` 保存会话（body 包含 `user_id` 与 `session` 对象）
  - `GET /api/v1/sessions/{user_id}` 列表
  - `GET /api/v1/sessions/{user_id}/{session_id}` 获取单个会话
  - `DELETE /api/v1/sessions/{user_id}/{session_id}` 删除会话
- **前端行为**：若 localStorage 中存在 `medical_chat_user_id`，`chat` store 会在 `saveToStorage()` 时自动调用后端 `sessionAPI.saveSession` 同步当前会话。
- **验证**：

```
curl -X POST http://localhost:8000/api/v1/sessions -H "Content-Type: application/json" -d '{"user_id":"user123","session": {"id":"s1","title":"测试","messages":[]}}'
curl http://localhost:8000/api/v1/sessions/user123
```

### 4) KGPath 扩展（`source` 与 `confidence`）

- **说明**：`KGPath` 模型新增了 `source`（例如 `neo4j`/`memory`）和 `confidence`（0-1），后端在 `find_paths_for_query` 中会设置这些字段；前端 `EvidencePanel` 会展示来源和置信度以供排序/判断。
- **验证**：对返回 `kg_paths` 的查询打开证据面板，查看每条路径的来源与置信度信息。

### 5) 调试/排查建议

- 若搜索结果与预期不同，先在 Neo4j 中运行全文查询检查索引命中情况；检查后端日志中“Fulltext query failed”或“Fulltext search failed”的调试信息。
- 若记忆未生效：确认请求是否包含 `user_id`，并检查 `data/memories.db` 是否有新记录。
- 若会话未同步：检查浏览器 localStorage `medical_chat_user_id` 是否存在，并查看后端 `/api/v1/sessions/{user_id}` 返回。

---

<a id="logs"></a>

## 日志查看

### 查看实时日志

```bash
# 后端日志会自动输出到控制台
# 使用 loguru 格式化输出，包含时间、级别、模块信息
```

### 常见日志信息

```
INFO | Connected to Neo4j - Found 8807 diseases in knowledge graph
INFO | SiliconFlow client initialized (model: deepseek-ai/DeepSeek-V3)
INFO | Processing query [q_abc123def456]: 头痛两天，可能是什么原因？...
DEBUG | Extracted entities: ['头痛']
DEBUG | Found 3 KG paths
WARNING | SiliconFlow call timed out after 60s, using fallback
ERROR | SiliconFlow generation failed: API error...
```

---

## 架构说明

### 服务层次

```
API 层 (FastAPI Router)
    ↓
业务服务层 (QAService)
    ↓
数据服务层 (KGService, VectorService)
    ↓
数据存储 (Neo4j, 向量数据库)
```

### 请求处理流程

1. **接收请求** → API 端点接收用户查询
2. **实体提取** → 从查询中提取医学实体（规则+知识图谱搜索）
3. **知识检索** → 从知识图谱获取相关信息
4. **上下文构建** → 组合知识图谱数据和对话历史
5. **LLM 生成** → 调用大模型生成回答（带超时控制）
6. **返回响应** → 返回答案、证据、警告等信息

---

<a id="problem-7"></a>

## 问题 7：流式输出调试与优化

### 流式输出工作原理

项目使用 **Server-Sent Events (SSE)** 实现流式输出，让用户能够实时看到 AI 生成的内容，而不是等待完整回答。

#### 架构流程

```
前端 (Vue)
    ↓ POST /api/v1/query/stream
后端 API (FastAPI)
    ↓ StreamingResponse (SSE)
业务服务 (QAService)
    ↓ async generator (yield chunks)
LLM API (SiliconFlow/Gemini/OpenAI)
    ↓ stream=True
逐步返回内容块
```

#### 数据格式

后端发送的 SSE 数据格式：

```
data: {"status": "searching", "message": "正在检索知识图谱..."}\n\n
data: {"status": "evidence_found", "count": 3}\n\n
data: {"status": "generating", "message": "正在生成回答..."}\n\n
data: {"status": "content", "text": "根据"}\n\n
data: {"status": "content", "text": "知识图谱"}\n\n
data: {"status": "content", "text": "信息..."}\n\n
data: {"status": "complete", "response": {...}}\n\n
```

### 流式输出状态说明

| 状态             | 说明             | 数据字段                  |
| ---------------- | ---------------- | ------------------------- |
| `searching`      | 正在检索知识图谱 | `message`                 |
| `evidence_found` | 找到证据文献     | `count`                   |
| `generating`     | 正在生成回答     | `message`                 |
| `content`        | 内容块（可多次） | `text`                    |
| `complete`       | 流式完成         | `response` (完整响应对象) |
| `error`          | 发生错误         | `message`                 |

### 延迟控制

#### Mock 模式延迟

在 `backend/app/services/qa_service.py` 中，Mock 模式使用字符级延迟模拟打字效果：

```python
# 模拟流式输出
for char in answer:
    yield f"data: {json.dumps({'status': 'content', 'text': char}, ensure_ascii=False)}\n\n"
    full_answer += char
    await asyncio.sleep(0.01)  # 模拟打字效果，每个字符延迟 10 毫秒
```

**调整延迟：**

- **更流畅**：减小延迟值，如 `0.001`（1 毫秒）或 `0.002`（2 毫秒）
- **更慢/更卡**：增大延迟值，如 `0.05`（50 毫秒）或 `0.1`（100 毫秒）

#### 真实 LLM 流式输出

对于 SiliconFlow、Gemini、OpenAI 等真实 LLM，流式输出由 LLM 服务本身控制，通常：

- **SiliconFlow/OpenAI**：每个 token 立即返回，无额外延迟
- **Gemini**：每个 chunk 立即返回，无额外延迟

如需添加延迟控制，可以在 yield 之前添加：

```python
async for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        content = chunk.choices[0].delta.content
        full_answer += content
        yield f"data: {json.dumps({'status': 'content', 'text': content}, ensure_ascii=False)}\n\n"
        # 可选：添加延迟（单位：秒）
        # await asyncio.sleep(0.01)  # 10毫秒延迟
```

### 常见问题排查

#### 1. 流式输出不显示或卡顿

**可能原因：**

- 网络连接问题
- 浏览器缓冲
- Nginx 反向代理缓冲

**解决方案：**

检查后端响应头（已在代码中设置）：

```python
headers={
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # 禁用nginx缓冲
}
```

如果使用 Nginx，确保配置：

```nginx
proxy_buffering off;
proxy_cache off;
```

#### 2. 前端接收数据不完整

**检查点：**

1. 浏览器控制台是否有错误
2. SSE 连接是否正常建立
3. 数据解析是否正确

**调试方法：**

在前端 `api.js` 中添加日志：

```javascript
async streamQuery(queryData, onMessage, onError, onComplete, signal) {
    // ...
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            console.log('Received SSE data:', line)  // 添加日志
            try {
                const data = JSON.parse(line.slice(6))
                onMessage(data)
                // ...
            }
        }
    }
}
```

#### 3. 流式输出中断

**可能原因：**

- LLM API 超时
- 网络连接断开
- 后端异常

**检查后端日志：**

```bash
# 查看流式处理错误
grep "Stream processing failed" logs/app.log
```

#### 4. Mock 模式流式输出太快/太慢

**调整延迟：**

编辑 `backend/app/services/qa_service.py` 第 849 行：

```python
await asyncio.sleep(0.01)  # 修改这个值
```

**推荐值：**

- 流畅体验：`0.001` - `0.005` 秒
- 正常速度：`0.01` - `0.02` 秒
- 慢速演示：`0.05` - `0.1` 秒

### 测试流式输出

#### 1. 使用 curl 测试

```bash
# 测试流式输出端点
curl -X POST http://localhost:8000/api/v1/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "头痛怎么办？"}' \
  --no-buffer

# 输出示例：
# data: {"status": "searching", "message": "正在检索知识图谱..."}
#
# data: {"status": "generating", "message": "正在生成回答..."}
#
# data: {"status": "content", "text": "根据"}
#
# data: {"status": "content", "text": "知识图谱"}
# ...
```

#### 2. 使用浏览器测试

打开浏览器开发者工具（F12），在 Network 标签页中：

1. 发送一个查询请求
2. 找到 `/api/v1/query/stream` 请求
3. 点击查看 Response，应该能看到逐步返回的数据

#### 3. 前端调试

在浏览器控制台中：

```javascript
// 监听流式数据
queryAPI.streamQuery(
  { query: "测试问题" },
  (data) => console.log("收到数据:", data),
  (err) => console.error("错误:", err),
  (response) => console.log("完成:", response)
);
```

### 性能优化建议

1. **减少不必要的延迟**

   - Mock 模式：根据需求调整 `asyncio.sleep()` 的值
   - 真实 LLM：通常不需要额外延迟

2. **批量发送内容**

   - 对于真实 LLM，可以累积多个 token 后一次性发送，减少网络开销
   - 但会影响实时性，需要权衡

3. **错误处理**

   - 确保流式输出中的异常能被正确捕获和报告
   - 使用 `try-except` 包裹 yield 语句

4. **连接管理**
   - 前端使用 `AbortController` 支持取消请求
   - 后端使用信号量控制并发数

### 流式输出代码位置

- **后端 API 端点**：`backend/app/api/v1/endpoints/query.py` (第 42-68 行)
- **业务逻辑**：`backend/app/services/qa_service.py` (第 738-1032 行)
- **前端 API 调用**：`frontend/src/services/api.js` (第 42-99 行)
- **前端状态管理**：`frontend/src/stores/chat.js` (第 231-399 行)

---

<a id="implementation-details"></a>

## 实现细节与调试要点（详述） 🔍

下面按功能模块详细说明实现逻辑、关键代码位置、调试建议与验证步骤，便于开发者快速定位与排查。

### A. 知识图谱检索（全文索引优先 | 回退 CONTAINS）

- **实现逻辑**：在 `backend/app/services/kg_service.py` 中实现 `_fulltext_query_nodes`。对 `search_disease` / `search_symptom` 优先调用：

```cypher
CALL db.index.fulltext.queryNodes("kg_fulltext", $query) YIELD node, score
WHERE 'Disease' IN labels(node)
RETURN node, score
ORDER BY score DESC
LIMIT $limit
```

- **回退策略**：若全文索引不可用或查询异常，函数捕获异常并记录 `logger.debug('Fulltext search failed, falling back to CONTAINS', exc_info=True)`，随后执行带 `IS NOT NULL` 的 `CONTAINS` 查询以保证兼容性。

- **调试/验证**：使用 Neo4j 控制台执行 `CALL db.index.fulltext.queryNodes(...)` 测试；查看后端日志是否输出 “Fulltext query failed”。

### B. `KGPath` 扩展（`source` 与 `confidence`）

- **实现逻辑**：`backend/app/models/query.py` 中 `KGPath` 增加 `source: Optional[str]` 和 `confidence: float`。
- **置信度计算**：对每条路径采用启发式评分（例如：路径长度、关系类型权重、全文 score、记忆来源优先级），归一化到 [0,1]。示例：
  - fulltext score 映射为基础分；
  - 若来自 `memory_service`，加权 +0.1；
  - 根据路径 hop 数目做衰减。
- **调试/验证**：前端 `EvidencePanel` 会展示 `source` 与 `confidence`；在日志中打印每条路径的评分信息以便回测。

### C. 短期记忆服务（`memory_service`）

- **实现逻辑** (`backend/app/services/memory_service.py`)：

  - 使用 SQLite (`data/memories.db`) 存储简要记忆片段（时间戳、用户 id、摘要、原始文本）。
  - 检索使用简单相似度（`difflib.SequenceMatcher`）或基于 token 的匹配，返回 top-k 结果并带相似度分数。
  - 在 `qa_service` 中，在构建 `kg_context` 之前调用 `memory_service.search_memory(user_id, query)`，若高相似度记忆存在则把记忆片段插入 `evidence_context` 或 `kg_context`。

- **触发与写入**：请求体包含 `user_id` 时，响应完成后异步写入记忆（摘要而非原始整条对话），避免写入过大文本。写入逻辑对频繁重复内容做去重/合并。

- **调试/验证**：
  1. 发起带 `user_id` 的请求，完成后检查 `data/memories.db` 或后端日志（包含 `Memory saved` 行）。
  2. 发起相关查询，观察流或最终回答是否包含对应记忆片段。

### D. 会话持久化（`session_service`）

- **实现逻辑** (`backend/app/services/session_service.py`)：

  - REST API：`POST /api/v1/sessions`、`GET /api/v1/sessions/{user_id}`、`GET /{user_id}/{session_id}`、`DELETE /{user_id}/{session_id}`。
  - 前端 `chat` store（`frontend/src/stores/chat.js`）在 `saveToStorage()` 检测到 `medical_chat_user_id` 时，会把当前会话对象同步到后端。

- **调试/验证**：使用 `curl` 调用 session API，或在浏览器 localStorage 中设置 `medical_chat_user_id` 并浏览后端 sessions 列表。

### E. 实体抽取与历史回溯（共指/省略恢复）

- **实现逻辑** (`backend/app/services/qa_service.py`)：

  - 三阶段实体提取：
    1. 静态词表/正则匹配（快速）；
    2. 针对每个候选短词调用 KG 搜索（全文优先）匹配疾病/症状；
    3. 若第一轮无结果，回溯最近用户消息（最多 6 条）对每条做同样的实体提取（history backtrace），并在必要时把历史与当前 query 合并再尝试一次检索。
  - 去重并保持发现顺序，返回给 `find_paths_for_query`。

- **调试/验证**：在后端增加 `DEBUG | Extracted entities` 日志可观察每一步的输出；复现场景如：先问“肺炎有哪些症状”，再问“那应该吃什么药治疗”，应能从历史识别“肺炎”。

### F. 多会话并发与流式取消（前端修复）

- **问题根因**：原实现使用单一全局 AbortController 与对 `currentSession.value` 的隐式引用，导致切换会话或并行请求时出现互相取消、流式内容丢失或错误的 isLoading 状态。

- **实现逻辑**（前端）：

  - `frontend/src/stores/chat.js`：维护 `abortControllers = { [sessionId]: AbortController }` 的映射；提供 `setAbortController(sessionId, controller)`, `getAbortController(sessionId)`, `clearAbortController(sessionId)`。
  - `sendMessage()` 使用本会话的 `session = sessions.find(s => s.id === sessionId)` 局部变量操作（所有消息读写均作用于 `session.messages`），并把 `controller` 绑定到 `sessionId`，从而保证取消/完成只影响指定会话。
  - `ChatView` 中的发送按钮（图标、提示文本）已改为使用 `isCurrentLoading`（会话级别），避免其他会话的 loading 状态影响当前会话的按钮显示与行为。

- **调试/验证**：在浏览器中同时对会话 A/B 发起流式请求，切换聚焦，验证两个流能并行且互不干扰；使用浏览器 console 查看是否有 `AbortError` 被错误触发且仅出现在目标会话。

**通俗讲**：原来把“取消当前请求”的开关做成全局的，就像家里只有一个遥控器，换到另一个房间时按了遥控器会把其他房间的电视也关掉。现在每个会话都有自己的遥控器（每个会话一个 AbortController），你在会话 A 操作或取消时，不会影响会话 B 的播放，两个对话可以同时进行。

**更简单的验证步骤**：

1. 在会话 A 中发送一个需要较长时间（或有明显流式输出）的查询（例如包含证据检索或使用慢模型）。
2. 立即切换到会话 B 并发送另一个查询。
3. 观察会话 A 与 B 是否都能持续收到流式输出，且互不干扰。
4. 在会话 A 点击取消（或切换并触发取消），确认只会中断 A 的流，美国（B）仍在继续；同时在浏览器 Console 可看到仅 A 出现 `AbortError` 的日志。

（注：这一改动旨在避免会话之间的相互影响，提高并发多对话时的稳定性。）

### G. 流式渲染（Mermaid 图像渲染失败的说明）

- **已尝试**：本地使用 `npx @mermaid-js/mermaid-cli -i docs/flow.mmd -o docs/flow.png` 尝试渲染但失败，错误原因为 npm 缓存/权限（EPERM）导致 `npx` 无法完成安装。

- **建议方案**：
  1. 使用在线工具 `https://mermaid.live/` 粘贴 `.mmd` 内容并导出 PNG；
  2. 在能访问 npm 的环境重试并确保 `npm cache clean --force` 有权限或以管理员身份运行；
  3. 或在 CI 中做渲染（容器中安装 mermaid-cli）以避免本地权限问题。

### H. 常用排查点（快速定位）

- 检查 Neo4j 索引是否存在：`CALL db.index.fulltext.queryNodes("kg_fulltext", "肺炎")`。
- 如果实体提取失败：查看后端日志中的 `Extracted entities` 与 `KG search` debug 行。
- 若会话丢失或未同步：检查 `medical_chat_user_id`、`/api/v1/sessions/{user_id}` 与 `localStorage` 保存时间是否一致。
- 若流式输出被取消：检查前端是否有对应会话的 AbortController 被 `.abort()`，并查看控制台是否有 `AbortError` 日志行。

### I. 未来可选优化（短述）

- 用 Embeddings + 向量数据库替换 `memory_service` 中的简单相似度检索以提高召回率；
- 使用更强的中文共指解析模型减少误判；
- 把 `KGPath` 的置信度计算替换为学习模型（基于历史打分数据训练）。

---

_最后更新：2025-12-27（新增实现细节与调试要点）_
