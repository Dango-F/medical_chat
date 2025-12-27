"""Knowledge Graph API Endpoints"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.models.kg import (
    NodeResponse,
    NodeNeighborsResponse,
    SearchNodesRequest,
    SearchNodesResponse,
    GraphStatsResponse
)
from app.services.kg_service import kg_service

router = APIRouter()


@router.get("/node/{node_id}", response_model=NodeNeighborsResponse)
async def get_node(node_id: str):
    """
    获取知识图谱节点详情及其邻居

    - **node_id**: 节点ID（如 D001, S001, DR001 等）

    返回节点的完整信息和所有连接的邻居节点
    """
    try:
        result = await kg_service.get_node_neighbors(node_id)
        if not result.node or result.node.label == "Not Found":
            raise HTTPException(status_code=404, detail=f"节点 {node_id} 未找到")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get node {node_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=SearchNodesResponse)
async def search_nodes(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    types: Optional[str] = Query(
        None, description="节点类型，逗号分隔（Disease,Drug,Symptom等）"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制")
):
    """
    搜索知识图谱节点

    - **q**: 搜索关键词
    - **types**: 可选，过滤节点类型（逗号分隔）
    - **limit**: 返回数量限制

    返回匹配的节点列表
    """
    try:
        node_types = types.split(",") if types else None
        nodes = await kg_service.search_nodes(q, node_types=node_types, limit=limit)
        return SearchNodesResponse(
            nodes=nodes,
            total=len(nodes),
            query=q
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph")
async def get_graph_data(
    limit: int = Query(100, ge=50, le=500, description="节点数量限制（总节点数，50-500）")
):
    """
    获取知识图谱可视化数据（返回总节点数受 `limit` 控制）

    返回节点和边的数据，用于前端图可视化
    """
    try:
        data = await kg_service.get_graph_data(limit=limit)
        return data
    except Exception as e:
        logger.error(f"Failed to get graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats():
    """
    获取知识图谱统计信息

    返回节点和关系的数量统计（全库真实数据）
    """
    try:
        # 使用真实的数据库统计，而不是采样数据
        stats = await kg_service.get_statistics()

        # 计算总节点数
        total_nodes = sum(count for key, count in stats.items()
                          if key != "total_relationships")

        # 节点类型统计
        node_types = {key: count for key, count in stats.items()
                      if key != "total_relationships"}

        # 关系数量
        total_relationships = stats.get("total_relationships", 0)

        return GraphStatsResponse(
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            node_types=node_types,
            relationship_types={}  # 暂不统计关系类型详情，避免性能问题
        )
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def get_node_types():
    """
    获取所有节点类型

    返回知识图谱中的实体类型列表及其描述
    """
    return {
        "types": [
            {"id": "Disease", "label": "疾病", "color": "#ef4444",
                "description": "疾病实体，如偏头痛、糖尿病"},
            {"id": "Symptom", "label": "症状", "color": "#f97316",
                "description": "症状表现，如头痛、发热"},
            {"id": "Drug", "label": "药物", "color": "#22c55e",
                "description": "药物实体，如布洛芬、二甲双胍"},
            {"id": "Food", "label": "食物", "color": "#eab308",
                "description": "饮食相关，宜吃/忌吃食物"},
            {"id": "Check", "label": "检查", "color": "#3b82f6",
                "description": "检查项目，如血常规、CT"},
            {"id": "Department", "label": "科室",
                "color": "#8b5cf6", "description": "医院科室，如内科、外科"},
            {"id": "Cure", "label": "治疗", "color": "#14b8a6", "description": "治疗方法"},
            {"id": "Producer", "label": "生产商",
                "color": "#6366f1", "description": "药品生产厂商"}
        ]
    }


@router.get("/relationships")
async def get_relationship_types():
    """
    获取所有关系类型

    返回知识图谱中的关系类型列表及其描述
    """
    return {
        "types": [
            {"id": "HAS_SYMPTOM", "label": "有症状", "description": "疾病与症状的关联"},
            {"id": "TREATS", "label": "治疗", "description": "药物用于治疗疾病"},
            {"id": "COVERS", "label": "涵盖", "description": "指南涵盖的疾病"},
            {"id": "DESCRIBES", "label": "描述", "description": "文献描述的实体"},
            {"id": "INDICATES", "label": "提示", "description": "危险信号提示的疾病"},
            {"id": "CONTRAINDICATED", "label": "禁忌", "description": "药物禁忌症"}
        ]
    }
