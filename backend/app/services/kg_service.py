# coding: utf-8
"""Knowledge Graph Service - Neo4j integration for Medical KG"""

from typing import List, Dict, Any, Optional
from loguru import logger

from app.core.config import settings
from app.models.query import KGNode, KGEdge, KGPath
from app.models.kg import NodeResponse, NeighborNode, NodeNeighborsResponse


class KnowledgeGraphService:
    """Service for interacting with the medical knowledge graph"""

    def __init__(self):
        self.driver = None
        self._is_connected = False
        self._mock_mode = False  # 默认使用真实知识图谱

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def initialize(self):
        """Initialize Neo4j connection"""
        try:
            from neo4j import AsyncGraphDatabase
            self.driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            # Test connection
            async with self.driver.session() as session:
                result = await session.run("MATCH (n:Disease) RETURN count(n) as count")
                record = await result.single()
                count = record["count"] if record else 0
                logger.info(
                    f"Connected to Neo4j - Found {count} diseases in knowledge graph")
            self._is_connected = True
        except Exception as e:
            logger.warning(
                f"Failed to connect to Neo4j: {e}. Some features may be limited.")
            self._is_connected = False

    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
        self._is_connected = False

    # ==================== 疾病查询 ====================

    async def get_disease_info(self, disease_name: str) -> Optional[Dict[str, Any]]:
        """获取疾病的完整信息"""
        if not self._is_connected:
            return None

        query = """
        MATCH (d:Disease {name: $name})
        RETURN d.name as name, d.desc as description, d.cause as cause,
               d.prevent as prevent, d.cure_lasttime as cure_time,
               d.cured_prob as cure_prob, d.easy_get as easy_get
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, name=disease_name)
                record = await result.single()
                if record:
                    return dict(record)
        except Exception as e:
            logger.error(f"Error getting disease info: {e}")
        return None

    async def get_disease_symptoms(self, disease_name: str) -> List[str]:
        """获取疾病的症状"""
        if not self._is_connected:
            return []

        query = """
        MATCH (d:Disease {name: $name})-[:has_symptom]->(s:Symptom)
        RETURN s.name as symptom
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, name=disease_name)
                records = await result.data()
                return [r["symptom"] for r in records]
        except Exception as e:
            logger.error(f"Error getting symptoms: {e}")
        return []

    async def get_disease_drugs(self, disease_name: str) -> Dict[str, List[str]]:
        """获取疾病的用药信息（常用药和推荐药）"""
        if not self._is_connected:
            return {"common": [], "recommended": []}

        common_query = """
        MATCH (d:Disease {name: $name})-[:common_drug]->(dr:Drug)
        RETURN dr.name as drug
        """
        recommend_query = """
        MATCH (d:Disease {name: $name})-[:recommand_drug]->(dr:Drug)
        RETURN dr.name as drug
        """
        try:
            async with self.driver.session() as session:
                common_result = await session.run(common_query, name=disease_name)
                common_records = await common_result.data()

                recommend_result = await session.run(recommend_query, name=disease_name)
                recommend_records = await recommend_result.data()

                return {
                    "common": [r["drug"] for r in common_records],
                    "recommended": [r["drug"] for r in recommend_records]
                }
        except Exception as e:
            logger.error(f"Error getting drugs: {e}")
        return {"common": [], "recommended": []}

    async def get_disease_foods(self, disease_name: str) -> Dict[str, List[str]]:
        """获取疾病的饮食建议（宜吃、忌吃、推荐）"""
        if not self._is_connected:
            return {"do_eat": [], "not_eat": [], "recommended": []}

        try:
            async with self.driver.session() as session:
                # 宜吃
                do_eat_query = "MATCH (d:Disease {name: $name})-[:do_eat]->(f:Food) RETURN f.name as food"
                do_eat_result = await session.run(do_eat_query, name=disease_name)
                do_eat = [r["food"] for r in await do_eat_result.data()]

                # 忌吃
                not_eat_query = "MATCH (d:Disease {name: $name})-[:no_eat]->(f:Food) RETURN f.name as food"
                not_eat_result = await session.run(not_eat_query, name=disease_name)
                not_eat = [r["food"] for r in await not_eat_result.data()]

                # 推荐
                recommend_query = "MATCH (d:Disease {name: $name})-[:recommand_eat]->(f:Food) RETURN f.name as food"
                recommend_result = await session.run(recommend_query, name=disease_name)
                recommended = [r["food"] for r in await recommend_result.data()]

                return {
                    "do_eat": do_eat,
                    "not_eat": not_eat,
                    "recommended": recommended
                }
        except Exception as e:
            logger.error(f"Error getting foods: {e}")
        return {"do_eat": [], "not_eat": [], "recommended": []}

    async def get_disease_checks(self, disease_name: str) -> List[str]:
        """获取疾病的检查项目"""
        if not self._is_connected:
            return []

        query = """
        MATCH (d:Disease {name: $name})-[:need_check]->(c:Check)
        RETURN c.name as check_item
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, name=disease_name)
                records = await result.data()
                return [r["check_item"] for r in records]
        except Exception as e:
            logger.error(f"Error getting checks: {e}")
        return []

    async def get_disease_department(self, disease_name: str) -> List[str]:
        """获取疾病所属科室"""
        if not self._is_connected:
            return []

        query = """
        MATCH (d:Disease {name: $name})-[:belongs_to]->(dep:Department)
        RETURN dep.name as department
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, name=disease_name)
                records = await result.data()
                return [r["department"] for r in records]
        except Exception as e:
            logger.error(f"Error getting department: {e}")
        return []

    async def get_disease_cure_ways(self, disease_name: str) -> List[str]:
        """获取疾病的治疗方法"""
        if not self._is_connected:
            return []

        query = """
        MATCH (d:Disease {name: $name})-[:cure_way]->(c:Cure)
        RETURN c.name as cure_way
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, name=disease_name)
                records = await result.data()
                return [r["cure_way"] for r in records]
        except Exception as e:
            logger.error(f"Error getting cure ways: {e}")
        return []

    async def get_disease_complications(self, disease_name: str) -> List[str]:
        """获取疾病的并发症"""
        if not self._is_connected:
            return []

        query = """
        MATCH (d:Disease {name: $name})-[:acompany_with]->(d2:Disease)
        RETURN d2.name as complication
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, name=disease_name)
                records = await result.data()
                return [r["complication"] for r in records]
        except Exception as e:
            logger.error(f"Error getting complications: {e}")
        return []

    # ==================== 症状查询 ====================

    async def get_diseases_by_symptom(self, symptom_name: str) -> List[str]:
        """根据症状查找可能的疾病"""
        if not self._is_connected:
            return []

        query = """
        MATCH (d:Disease)-[:has_symptom]->(s:Symptom {name: $name})
        RETURN d.name as disease
        LIMIT 20
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, name=symptom_name)
                records = await result.data()
                return [r["disease"] for r in records]
        except Exception as e:
            logger.error(f"Error getting diseases by symptom: {e}")
        return []

    async def get_diseases_by_symptoms(self, symptoms: List[str]) -> List[Dict[str, Any]]:
        """根据多个症状查找可能的疾病，按匹配数量排序"""
        if not self._is_connected or not symptoms:
            return []

        query = """
        MATCH (d:Disease)-[:has_symptom]->(s:Symptom)
        WHERE s.name IN $symptoms
        WITH d, count(DISTINCT s) as match_count
        WHERE match_count > 0
        RETURN d.name as disease, match_count
        ORDER BY match_count DESC
        LIMIT 10
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, symptoms=symptoms)
                records = await result.data()
                return [{"disease": r["disease"], "match_count": r["match_count"]} for r in records]
        except Exception as e:
            logger.error(f"Error getting diseases by symptoms: {e}")
        return []

    # ==================== 搜索功能 ====================

    async def _fulltext_query_nodes(self, index_name: str, query_text: str, node_label: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Helper: run fulltext query and return list of {name, score}"""
        results: List[Dict[str, Any]] = []
        try:
            async with self.driver.session() as session:
                q = f"""
                CALL db.index.fulltext.queryNodes($index_name, $query) YIELD node, score
                WHERE $label IN labels(node)
                RETURN node.name AS name, score
                ORDER BY score DESC
                LIMIT $limit
                """
                result = await session.run(q, index_name=index_name, query=query_text, label=node_label, limit=limit)
                records = await result.data()
                for r in records:
                    results.append(
                        {"name": r.get("name"), "score": r.get("score", 0)})
        except Exception as e:
            logger.debug(f"Fulltext query failed (index may be missing): {e}")
        return results

    async def search_disease(self, keyword: str, limit: int = 10) -> List[str]:
        """模糊搜索疾病名称（优先使用精确匹配 -> 全文索引 -> CONTAINS；并对结果按相关性排序）"""
        if not self._is_connected:
            return []

        # 归一化关键字：去掉常见修饰词（例如“普通”、“常见”、“季节性”等），以提高匹配准确性
        try:
            import re
            norm_kw = keyword
            for w in ["普通", "常见", "季节性", "一般", "常规"]:
                norm_kw = norm_kw.replace(w, "")
            norm_kw = norm_kw.strip()
        except Exception:
            norm_kw = keyword

        # 1) 尝试精确匹配（名称或别名完全相等）
        try:
            exact_q = """
            MATCH (d:Disease)
            WHERE d.name = $kw OR (d.alias IS NOT NULL AND any(a IN d.alias WHERE a = $kw))
            RETURN d.name as name
            LIMIT $limit
            """
            async with self.driver.session() as session:
                result = await session.run(exact_q, kw=keyword, limit=limit)
                records = await result.data()
                if records:
                    return [r["name"] for r in records]

                # 如果原始关键字未命中，尝试归一化后的关键字
                if norm_kw and norm_kw != keyword:
                    result = await session.run(exact_q, kw=norm_kw, limit=limit)
                    records = await result.data()
                    if records:
                        return [r["name"] for r in records]
        except Exception as e:
            logger.debug(f"Exact match search failed: {e}")

        # 2) 尝试全文索引（需要管理员在 Neo4j 中创建名为 `kg_fulltext` 的索引）
        try:
            ft_results = await self._fulltext_query_nodes("kg_fulltext", keyword, "Disease", limit)
            if ft_results:
                names = [r["name"] for r in ft_results][:limit]
                return names

            # 尝试归一化关键字的全文检索
            if norm_kw and norm_kw != keyword:
                ft_results = await self._fulltext_query_nodes("kg_fulltext", norm_kw, "Disease", limit)
                if ft_results:
                    return [r["name"] for r in ft_results][:limit]
        except Exception:
            logger.debug("Fulltext search errored, falling back to CONTAINS")

        # 3) 回退到 CONTAINS 查询，但按相关性排序：精确=0, startswith=1, contains=2
        query = """
        MATCH (d:Disease)
        WHERE d.name CONTAINS $keyword OR (d.alias IS NOT NULL AND any(a IN d.alias WHERE a CONTAINS $keyword))
        RETURN d.name as name,
               CASE
                 WHEN d.name = $keyword THEN 0
                 WHEN d.name STARTS WITH $keyword THEN 1
                 WHEN d.name CONTAINS $keyword THEN 2
                 ELSE 3
               END AS rank
        ORDER BY rank, d.name
        LIMIT $limit
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, keyword=keyword, limit=limit)
                records = await result.data()
                names = [r["name"] for r in records]

                # 如果没有充分匹配，再尝试用归一化关键字
                if not names and norm_kw and norm_kw != keyword:
                    result = await session.run(query, keyword=norm_kw, limit=limit)
                    records = await result.data()
                    names = [r["name"] for r in records]

                return names
        except Exception as e:
            logger.error(f"Error searching disease: {e}")
        return []

    async def search_symptom(self, keyword: str, limit: int = 10) -> List[str]:
        """模糊搜索症状（优先尝试全文索引）"""
        if not self._is_connected:
            return []

        try:
            ft_results = await self._fulltext_query_nodes("kg_fulltext", keyword, "Symptom", limit)
            if ft_results:
                return [r["name"] for r in ft_results][:limit]
        except Exception:
            logger.debug(
                "Fulltext symptom search errored, falling back to CONTAINS")

        query = """
        MATCH (s:Symptom)
        WHERE s.name CONTAINS $keyword OR (s.alias IS NOT NULL AND any(a IN s.alias WHERE a CONTAINS $keyword))
        RETURN s.name as name
        LIMIT $limit
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query, keyword=keyword, limit=limit)
                records = await result.data()
                return [r["name"] for r in records]
        except Exception as e:
            logger.error(f"Error searching symptom: {e}")
        return []

    # ==================== 综合查询 ====================

    async def get_full_disease_info(self, disease_name: str) -> Optional[Dict[str, Any]]:
        """获取疾病的完整信息（包含所有关联数据）"""
        if not self._is_connected:
            return None

        # 先检查疾病是否存在
        basic_info = await self.get_disease_info(disease_name)
        if not basic_info:
            # 尝试模糊匹配
            matches = await self.search_disease(disease_name, limit=1)
            if matches:
                disease_name = matches[0]
                basic_info = await self.get_disease_info(disease_name)
            if not basic_info:
                return None

        # 并行获取所有关联信息，提高并发性能
        import asyncio
        (
            symptoms,
            drugs,
            foods,
            checks,
            departments,
            cure_ways,
            complications
        ) = await asyncio.gather(
            self.get_disease_symptoms(disease_name),
            self.get_disease_drugs(disease_name),
            self.get_disease_foods(disease_name),
            self.get_disease_checks(disease_name),
            self.get_disease_department(disease_name),
            self.get_disease_cure_ways(disease_name),
            self.get_disease_complications(disease_name)
        )

        return {
            "name": disease_name,
            "description": basic_info.get("description", ""),
            "cause": basic_info.get("cause", ""),
            "prevent": basic_info.get("prevent", ""),
            "cure_time": basic_info.get("cure_time", ""),
            "cure_prob": basic_info.get("cure_prob", ""),
            "easy_get": basic_info.get("easy_get", ""),
            "symptoms": symptoms,
            "common_drugs": drugs.get("common", []),
            "recommended_drugs": drugs.get("recommended", []),
            "do_eat": foods.get("do_eat", []),
            "not_eat": foods.get("not_eat", []),
            "recommended_foods": foods.get("recommended", []),
            "checks": checks,
            "departments": departments,
            "cure_ways": cure_ways,
            "complications": complications
        }

    # ==================== 为问答系统提供的接口 ====================

    async def find_paths_for_query(self, entities: List[str]) -> List[KGPath]:
        """为问答系统查找相关的知识图谱路径"""
        paths = []

        if not self._is_connected:
            return paths

        for entity in entities[:5]:  # 限制实体数量
            # 尝试作为疾病查询
            disease_info = await self.get_full_disease_info(entity)
            if disease_info and disease_info.get("description"):
                # 构建疾病相关路径
                nodes = [KGNode(
                    id=f"disease_{entity}",
                    label=disease_info["name"],
                    type="Disease",
                    properties={
                        "description": disease_info.get("description", ""),
                        "cause": disease_info.get("cause", ""),
                        "prevent": disease_info.get("prevent", "")
                    }
                )]
                edges = []

                # 添加症状节点
                for symptom in disease_info.get("symptoms", [])[:5]:
                    nodes.append(KGNode(
                        id=f"symptom_{symptom}",
                        label=symptom,
                        type="Symptom",
                        properties={}
                    ))
                    edges.append(KGEdge(
                        source=f"disease_{entity}",
                        target=f"symptom_{symptom}",
                        type="has_symptom",
                        properties={"name": "症状"}
                    ))

                # 添加药物节点
                all_drugs = disease_info.get(
                    "common_drugs", []) + disease_info.get("recommended_drugs", [])
                for drug in all_drugs[:3]:
                    nodes.append(KGNode(
                        id=f"drug_{drug}",
                        label=drug,
                        type="Drug",
                        properties={}
                    ))
                    edges.append(KGEdge(
                        source=f"disease_{entity}",
                        target=f"drug_{drug}",
                        type="common_drug",
                        properties={"name": "常用药品"}
                    ))

                paths.append(KGPath(
                    nodes=nodes,
                    edges=edges,
                    relevance_score=0.9,
                    source="neo4j",
                    confidence=0.9
                ))
                continue

            # 尝试作为症状查询
            diseases = await self.get_diseases_by_symptom(entity)
            if diseases:
                nodes = [KGNode(
                    id=f"symptom_{entity}",
                    label=entity,
                    type="Symptom",
                    properties={}
                )]
                edges = []

                for disease in diseases[:5]:
                    nodes.append(KGNode(
                        id=f"disease_{disease}",
                        label=disease,
                        type="Disease",
                        properties={}
                    ))
                    edges.append(KGEdge(
                        source=f"disease_{disease}",
                        target=f"symptom_{entity}",
                        type="has_symptom",
                        properties={"name": "症状"}
                    ))

                paths.append(KGPath(
                    nodes=nodes,
                    edges=edges,
                    relevance_score=0.8,
                    source="neo4j",
                    confidence=0.8
                ))

        return paths[:5]

    async def get_kg_context_for_query(self, entities: List[str]) -> str:
        """为问答系统生成知识图谱上下文"""
        if not self._is_connected:
            return ""

        context_parts = []

        for entity in entities[:3]:
            # 尝试获取疾病信息
            disease_info = await self.get_full_disease_info(entity)
            if disease_info and disease_info.get("description"):
                context = f"\n【{disease_info['name']}】\n"
                if disease_info.get("description"):
                    context += f"简介：{disease_info['description']}\n"
                if disease_info.get("symptoms"):
                    context += f"症状：{', '.join(disease_info['symptoms'][:10])}\n"
                if disease_info.get("cause"):
                    context += f"病因：{disease_info['cause'][:200]}...\n" if len(
                        disease_info.get('cause', '')) > 200 else f"病因：{disease_info['cause']}\n"
                if disease_info.get("prevent"):
                    context += f"预防：{disease_info['prevent'][:200]}...\n" if len(
                        disease_info.get('prevent', '')) > 200 else f"预防：{disease_info['prevent']}\n"
                if disease_info.get("departments"):
                    context += f"就诊科室：{', '.join(disease_info['departments'])}\n"
                if disease_info.get("cure_ways"):
                    context += f"治疗方法：{', '.join(disease_info['cure_ways'][:5])}\n"
                if disease_info.get("common_drugs") or disease_info.get("recommended_drugs"):
                    all_drugs = disease_info.get(
                        "common_drugs", []) + disease_info.get("recommended_drugs", [])
                    context += f"常用药物：{', '.join(all_drugs[:8])}\n"
                if disease_info.get("do_eat"):
                    context += f"宜吃食物：{', '.join(disease_info['do_eat'][:5])}\n"
                if disease_info.get("not_eat"):
                    context += f"忌吃食物：{', '.join(disease_info['not_eat'][:5])}\n"
                if disease_info.get("checks"):
                    context += f"检查项目：{', '.join(disease_info['checks'][:5])}\n"
                if disease_info.get("complications"):
                    context += f"并发症：{', '.join(disease_info['complications'][:5])}\n"

                context_parts.append(context)
                continue

            # 尝试症状查询
            diseases = await self.get_diseases_by_symptom(entity)
            if diseases:
                context = f"\n【症状：{entity}】\n"
                context += f"可能相关的疾病：{', '.join(diseases[:10])}\n"
                context_parts.append(context)

        return "\n".join(context_parts)

    # ==================== 统计信息 ====================

    async def get_statistics(self) -> Dict[str, int]:
        """获取知识图谱统计信息"""
        if not self._is_connected:
            return {}

        stats = {}
        labels = ["Disease", "Symptom", "Drug", "Food",
                  "Check", "Department", "Cure", "Producer"]

        try:
            async with self.driver.session() as session:
                for label in labels:
                    query = f"MATCH (n:{label}) RETURN count(n) as count"
                    result = await session.run(query)
                    record = await result.single()
                    if record:
                        stats[label] = record["count"]

                # 统计关系数量
                rel_query = "MATCH ()-[r]->() RETURN count(r) as count"
                result = await session.run(rel_query)
                record = await result.single()
                if record:
                    stats["total_relationships"] = record["count"]

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")

        return stats

    # ==================== 图可视化接口 ====================

    async def get_graph_data(self, limit: int = 100) -> Dict[str, Any]:
        """获取知识图谱可视化数据，从疾病节点出发，展示所有类型的关系"""
        if not self._is_connected:
            return {"nodes": [], "edges": []}

        nodes = []
        edges = []
        node_ids = set()

        # 节点类型到颜色的映射
        color_map = {
            "Disease": "#ef4444",
            "Symptom": "#f97316",
            "Drug": "#22c55e",
            "Food": "#eab308",
            "Check": "#3b82f6",
            "Department": "#8b5cf6",
            "Cure": "#14b8a6",
            "Producer": "#6366f1"
        }

        try:
            async with self.driver.session() as session:
                # 1. 先查limit个疾病节点
                disease_query = """
                MATCH (d:Disease)
                RETURN d.name as d_name, labels(d) as d_labels
                LIMIT $limit
                """
                disease_result = await session.run(disease_query, limit=limit)
                disease_records = await disease_result.data()

                disease_names = [rec['d_name'] for rec in disease_records]
                disease_label_map = {
                    rec['d_name']: rec['d_labels'] for rec in disease_records}

                # 2. 查这些疾病的所有出边和邻居节点
                if disease_names:
                    rel_query = """
                    MATCH (d:Disease)-[r]->(n)
                    WHERE d.name IN $disease_names
                    RETURN d.name as d_name, labels(d) as d_labels,
                           n.name as n_name, labels(n) as n_labels,
                           type(r) as rel_type
                    """
                    rel_result = await session.run(rel_query, disease_names=disease_names)
                    rel_records = await rel_result.data()

                    for record in rel_records:
                        d_name = record.get('d_name', 'unknown')
                        d_labels = record.get('d_labels', ['Unknown'])
                        n_name = record.get('n_name', 'unknown')
                        n_labels = record.get('n_labels', ['Unknown'])
                        rel_type = record.get('rel_type', 'related')

                        # 获取节点类型
                        d_type = d_labels[0] if d_labels else 'Unknown'
                        n_type = n_labels[0] if n_labels else 'Unknown'

                        # 添加疾病节点
                        d_id = f"disease_{d_name}"
                        if d_id not in node_ids:
                            node_ids.add(d_id)
                            nodes.append({
                                "id": d_id,
                                "label": d_name,
                                "type": d_type,
                                "color": color_map.get(d_type, "#6b7280")
                            })

                        # 添加关联节点
                        n_id = f"{n_type.lower()}_{n_name}"
                        if n_id not in node_ids:
                            node_ids.add(n_id)
                            nodes.append({
                                "id": n_id,
                                "label": n_name,
                                "type": n_type,
                                "color": color_map.get(n_type, "#6b7280")
                            })

                        # 添加边
                        edges.append({
                            "source": d_id,
                            "target": n_id,
                            "type": rel_type
                        })
                else:
                    # 没有疾病节点
                    pass
        except Exception as e:
            logger.error(f"Error getting graph data: {e}")

        # Ensure total returned nodes does not exceed requested limit
        if len(nodes) > limit:
            # Keep the first `limit` nodes and drop edges that reference any removed node
            allowed_nodes = nodes[:limit]
            allowed_ids = {n["id"] for n in allowed_nodes}
            edges = [e for e in edges if e["source"]
                     in allowed_ids and e["target"] in allowed_ids]
            nodes = allowed_nodes

        return {"nodes": nodes, "edges": edges}

    async def get_node_neighbors(self, node_id: str) -> NodeNeighborsResponse:
        """获取节点及其邻居"""
        if not self._is_connected:
            return NodeNeighborsResponse(
                node=NodeResponse(id=node_id, label="Not Found",
                                  type="Unknown", properties={}),
                neighbors=[]
            )

        try:
            async with self.driver.session() as session:
                # 先尝试按名称查找
                query = """
                MATCH (n)
                WHERE n.name = $name
                OPTIONAL MATCH (n)-[r]-(m)
                RETURN n, collect({node: m, rel: type(r)}) as neighbors
                LIMIT 1
                """
                result = await session.run(query, name=node_id)
                record = await result.single()

                if not record or not record['n']:
                    return NodeNeighborsResponse(
                        node=NodeResponse(
                            id=node_id, label="Not Found", type="Unknown", properties={}),
                        neighbors=[]
                    )

                n = record['n']
                n_labels = list(n.labels) if hasattr(
                    n, 'labels') else ['Unknown']

                node = NodeResponse(
                    id=node_id,
                    label=n.get('name', 'Unknown'),
                    type=n_labels[0] if n_labels else 'Unknown',
                    properties=dict(n)
                )

                neighbors = []
                for neighbor_data in record['neighbors']:
                    if neighbor_data['node']:
                        m = neighbor_data['node']
                        m_labels = list(m.labels) if hasattr(
                            m, 'labels') else ['Unknown']
                        neighbors.append(NeighborNode(
                            id=m.get('name', 'unknown'),
                            label=m.get('name', 'Unknown'),
                            type=m_labels[0] if m_labels else 'Unknown',
                            relationship=neighbor_data['rel']
                        ))

                return NodeNeighborsResponse(node=node, neighbors=neighbors)

        except Exception as e:
            logger.error(f"Error getting node neighbors: {e}")
            return NodeNeighborsResponse(
                node=NodeResponse(id=node_id, label="Error",
                                  type="Unknown", properties={}),
                neighbors=[]
            )

    async def search_nodes(self, keyword: str, node_types: Optional[List[str]] = None, limit: int = 20) -> List[NodeResponse]:
        """搜索节点"""
        if not self._is_connected:
            return []

        nodes = []

        try:
            async with self.driver.session() as session:
                if node_types:
                    # 搜索指定类型
                    for node_type in node_types:
                        query = f"""
                        MATCH (n:{node_type})
                        WHERE n.name CONTAINS $keyword
                        RETURN n
                        LIMIT $limit
                        """
                        result = await session.run(query, keyword=keyword, limit=limit)
                        records = await result.data()

                        for record in records:
                            n = record['n']
                            nodes.append(NodeResponse(
                                id=n.get('name', 'unknown'),
                                label=n.get('name', 'Unknown'),
                                type=node_type,
                                properties=dict(n)
                            ))
                else:
                    # 搜索所有类型
                    query = """
                    MATCH (n)
                    WHERE n.name CONTAINS $keyword
                    RETURN n, labels(n) as labels
                    LIMIT $limit
                    """
                    result = await session.run(query, keyword=keyword, limit=limit)
                    records = await result.data()

                    for record in records:
                        n = record['n']
                        labels = record['labels']
                        nodes.append(NodeResponse(
                            id=n.get('name', 'unknown'),
                            label=n.get('name', 'Unknown'),
                            type=labels[0] if labels else 'Unknown',
                            properties=dict(n)
                        ))

        except Exception as e:
            logger.error(f"Error searching nodes: {e}")

        return nodes[:limit]


# Singleton instance
kg_service = KnowledgeGraphService()
