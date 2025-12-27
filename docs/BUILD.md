# 构建知识图谱（diseasekg 目录分析）

本文档描述 `diseasekg` 目录中脚本的作用、构建流程、运行步骤与注意事项，便于维护与复现知识图谱的生成过程。

---

## 目录结构（摘录）

- build_json.py
- build_kg.py
- build_medicalgraph.py
- build_medicalgraph_from_json.py
- data/
  - medical.json
- dict/
  - disease.txt, symptom.txt, ...
- prepare_data/
  - build_data.py, data_spider.py, max_cut.py
- newdata/ (脚本运行时生成的中间 JSON)

---

## 核心脚本说明

### 1) `build_json.py`

- 作用：把 `data/medical.json` 中原始记录解析为两类中间 JSON：
  - `newdata/entities.json`（实体列表，带 label、name、部分属性）
  - `newdata/relations.json`（关系集合，按关系类型归类）
- 主要逻辑：
  - `read_nodes()`：从 `medical.json` 读取所有疾病记录并收集实体与关系（药物、食物、检查、科室、症状、治疗方法等）
  - `create_nodes_json()` / `create_rels_json()`：把集合格式化为标准 JSON 丢到 `newdata/`
- 适用场景：当你想先导出标准化 JSON（便于审阅或使用别的导入工具）时使用。

### 2) `build_kg.py` / `build_medicalgraph.py`

- 作用：直接读取 `data/medical.json`，并通过 `py2neo` 向 Neo4j 建立节点与关系。
- 区别：两者逻辑近似，`build_kg.py` 更完整一些（包含清空图、统计输出等）；`build_medicalgraph.py` 也含导出字典函数。
- 主要流程：
  1. `read_nodes()`：解析 `medical.json`，生成实体集合与关系边列表
  2. `create_graphnodes()`：依次创建 `Disease/Drug/Food/Check/Department/Producer/Symptom/Cure` 等节点（疾病节点包含详细属性）
  3. `create_graphrels()`：创建关系（如 `Disease` -[:has_symptom]-> `Symptom`）并写入 Neo4j
- 注意：脚本通过逐条 `CREATE` 或 `MATCH ... CREATE` 方式执行，数据量大时会很慢；脚本中对重复关系/节点没有做完全的去重与事务批量处理，建议在生产或大数据量时改用 bulk import 或 `UNWIND` 批量语句。

### 3) `build_medicalgraph_from_json.py`

- 作用：把 `newdata/entities.json` / `newdata/relations.json` 导入 Neo4j（JSON -> 图）
- 优点：先由 `build_json.py` 生成的结构化 JSON 更易校验，再通过此脚本导入；在需要中间审查/变更映射规则时更灵活。

### 4) `prepare_data/`（数据抓取与清洗）

- 包含：`build_data.py`（爬取或从 MongoDB 聚合原始数据并做字段映射）、`data_spider.py`（爬虫）、`max_cut.py`（中文分词或短语切分工具）。
- 作用：把采集到的原始 HTML/结构化数据归一化为 `medical.json` 中使用的字段与格式（例如把“症状”拆成数组、把“药品明细”拆为 `drug_detail` 等）

---

## 构建流程（推荐）

1. 准备环境
   - 安装 Python 3.8+、`py2neo`、`pymongo`（如需要）、以及其他依赖
   - 启动 Neo4j（记下 Bolt / HTTP 连接地址与密码）
2. （可选）用 `prepare_data/build_data.py` 从来源抓取并清洗数据到 MongoDB 或生成 `medical.json`
3. （可选）执行 `python build_json.py` 生成 `newdata/entities.json` 和 `newdata/relations.json`，便于审阅/测试
4. 直接导入到 Neo4j：
   - 方式 A（直接从 `medical.json`）：
     - `python build_kg.py` 或 `python build_medicalgraph.py`
     - 脚本会提示是否清空数据库（慎用）
   - 方式 B（先生成 JSON 再导入）：
     - `python build_json.py`
     - `python build_medicalgraph_from_json.py`
5. 验证（示例 Cypher）：
   - 简单检查：
     - `MATCH (n:Disease) RETURN n.name LIMIT 20` # 疾病节点
     - `MATCH (d:Disease)-[:has_symptom]->(s:Symptom) RETURN d.name, collect(s.name) LIMIT 5`
   - 全文索引（如需搜索）：
     - `CALL db.index.fulltext.createNodeIndex("kg_fulltext", ["Disease","Symptom"], ["name","alias","description"])`
     - `CALL db.index.fulltext.queryNodes("kg_fulltext", "流感") YIELD node, score RETURN node.name, score LIMIT 10`

---

## 验证与常见问题

- 性能慢：当前实现使用逐条 `CREATE` / `MATCH ... CREATE`，建议使用 `UNWIND` 批量插入或 Neo4j 提供的 CSV 批量导入工具以显著加速。
- 数据重复：检查脚本中去重策略（通常通过 `set()` 去重集合），但关系创建时仍可能重复。可在导入前使用 `apoc` 或 Cypher `MERGE` 做幂等插入。
- 编码/格式问题：确认 `medical.json` 为 UTF-8 且字段齐全；脚本对缺失字段默认空字符串或跳过。
- 连接失败：检查 Neo4j 启动、连接地址、用户名和密码，`py2neo` 的版本兼容性。

---

## 改进建议（工程化方向）

- 批量导入：把 `newdata/entities.json` / `relations.json` 转为 CSV，然后使用 Neo4j `neo4j-admin import` 或 `UNWIND` 批量导入。
- 索引与约束：为常用查询字段（`Disease.name`, `Symptom.name`, `Drug.name` 等）创建索引或唯一约束以提升查询性能与数据质量。
- 完善去重与归一化：加强别名映射（alias）、词形归一与繁简体处理，减少多条近似节点。
- 丰富节点属性：为节点增加 `source`、`confidence`、`last_updated` 等元信息以便溯源与更新。
- 测试与 CI：为 `prepare_data` -> `build_json` -> `import` 流程添加自动化测试，保证增量更新时不会破坏图结构。

---

## 常用命令（示例）

```bash
# 生成中间 JSON
python diseasekg/build_json.py

# 直接从 JSON 导入 Neo4j（newdata 下已生成 entities/relations）
python diseasekg/build_medicalgraph_from_json.py

# 或直接从原始 medical.json 导入
python diseasekg/build_kg.py

# 在 Neo4j 中创建全文索引
# （在 Neo4j Browser 或 cypher-shell 中执行）
CALL db.index.fulltext.createNodeIndex("kg_fulltext", ["Disease","Symptom"], ["name","alias","description"])
```

---

如果你希望，我可以：

- 把 `build_kg.py` 改为使用 `UNWIND` 批量创建以加速导入；或
- 添加一个小脚本用于导入后自动创建约束与全文索引，并输出基本统计；或
- 帮你写一个验证脚本来检查常见实体（如“流感”“小儿麻痹症”）是否正确导入。请选择下一步。
