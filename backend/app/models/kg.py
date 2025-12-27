"""Knowledge Graph models"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class NodeResponse(BaseModel):
    """Single node response"""
    id: str = Field(..., description="节点ID")
    label: str = Field(..., description="节点标签")
    type: str = Field(..., description="节点类型")
    properties: Dict[str, Any] = Field(default_factory=dict, description="节点属性")
    description: Optional[str] = Field(None, description="节点描述")
    aliases: List[str] = Field(default_factory=list, description="别名列表")
    external_ids: Dict[str, str] = Field(default_factory=dict, description="外部ID映射")


class NeighborNode(BaseModel):
    """Neighbor node with relationship info"""
    node: NodeResponse
    relationship_type: str = Field(..., description="关系类型")
    relationship_direction: str = Field(..., description="关系方向 (incoming/outgoing)")
    relationship_properties: Dict[str, Any] = Field(default_factory=dict)


class NodeNeighborsResponse(BaseModel):
    """Node with its neighbors"""
    node: NodeResponse
    neighbors: List[NeighborNode] = Field(default_factory=list, description="邻居节点列表")
    total_neighbors: int = Field(default=0, description="邻居总数")


class SearchNodesRequest(BaseModel):
    """Search nodes request"""
    query: str = Field(..., min_length=1, description="搜索关键词")
    node_types: Optional[List[str]] = Field(None, description="过滤节点类型")
    limit: int = Field(default=20, ge=1, le=100, description="返回数量限制")


class SearchNodesResponse(BaseModel):
    """Search nodes response"""
    nodes: List[NodeResponse] = Field(default_factory=list)
    total: int = Field(default=0)
    query: str


class GraphStatsResponse(BaseModel):
    """Knowledge graph statistics"""
    total_nodes: int = Field(..., description="节点总数")
    total_relationships: int = Field(..., description="关系总数")
    node_types: Dict[str, int] = Field(default_factory=dict, description="各类型节点数量")
    relationship_types: Dict[str, int] = Field(default_factory=dict, description="各类型关系数量")

