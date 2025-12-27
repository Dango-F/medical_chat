"""Query request and response models"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class SourceType(str, Enum):
    """Evidence source types"""
    PUBMED = "pubmed"
    GUIDELINE = "guideline"
    DRUGBANK = "drugbank"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    CLINICAL_TRIAL = "clinical_trial"
    WHO = "who"
    OTHER = "other"


class Evidence(BaseModel):
    """Evidence item with source information"""
    source: str = Field(..., description="来源名称")
    source_type: SourceType = Field(
        default=SourceType.OTHER, description="来源类型")
    snippet: str = Field(..., description="证据摘要片段")
    pmid: Optional[str] = Field(None, description="PubMed ID")
    doi: Optional[str] = Field(None, description="DOI")
    url: Optional[str] = Field(None, description="来源链接")
    confidence: float = Field(..., ge=0, le=1, description="置信度分数 (0-1)")
    publication_date: Optional[str] = Field(None, description="发布日期")
    section: Optional[str] = Field(None, description="章节/段落")


class KGNode(BaseModel):
    """Knowledge graph node"""
    id: str = Field(..., description="节点ID")
    label: str = Field(..., description="节点标签/名称")
    type: str = Field(..., description="节点类型 (Disease/Drug/Symptom等)")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="节点属性")


class KGEdge(BaseModel):
    """Knowledge graph edge/relationship"""
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    type: str = Field(..., description="关系类型")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="关系属性")


class KGPath(BaseModel):
    """Knowledge graph path"""
    nodes: List[KGNode] = Field(..., description="路径中的节点")
    edges: List[KGEdge] = Field(..., description="路径中的边")
    relevance_score: float = Field(default=1.0, description="相关性分数")
    source: Optional[str] = Field(
        default="neo4j", description="路径来源（如 neo4j/elasticsearch/memory）")
    confidence: float = Field(default=1.0, ge=0, le=1,
                              description="路径置信度（0-1）")


class ChatMessage(BaseModel):
    """Chat message for conversation history"""
    role: str = Field(..., description="消息角色 (user/assistant)")
    content: str = Field(..., description="消息内容")


class QueryRequest(BaseModel):
    """Query request model"""
    query: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    history: Optional[List[ChatMessage]] = Field(
        default=None, description="对话历史")
    user_id: Optional[str] = Field(None, description="用户ID")
    context: Optional[str] = Field(None, description="上下文信息")
    max_answers: int = Field(default=3, ge=1, le=10, description="最大回答数")
    include_kg_paths: bool = Field(default=True, description="是否包含知识图谱路径")
    include_evidence: bool = Field(default=True, description="是否包含证据")
    language: str = Field(default="zh", description="响应语言 (zh/en)")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "头痛两天，可能是什么原因？",
                "history": [
                    {"role": "user", "content": "我最近身体不太舒服"},
                    {"role": "assistant", "content": "请问您有什么具体症状呢？"}
                ],
                "max_answers": 3,
                "include_kg_paths": True
            }
        }


class AnswerSource(str, Enum):
    """Answer source types"""
    KNOWLEDGE_GRAPH = "knowledge_graph"  # 基于知识图谱
    LLM_ONLY = "llm_only"  # 纯大模型生成（知识图谱无数据）
    MIXED = "mixed"  # 混合来源
    TEMPLATE = "template"  # 模板回复（无LLM）


class QueryResponse(BaseModel):
    """Query response model"""
    query_id: str = Field(..., description="查询ID")
    answer: str = Field(..., description="生成的回答")
    answer_source: AnswerSource = Field(
        default=AnswerSource.KNOWLEDGE_GRAPH,
        description="回答来源: knowledge_graph(基于知识图谱) / llm_only(纯大模型) / mixed(混合) / template(模板)"
    )
    evidence: List[Evidence] = Field(default_factory=list, description="证据列表")
    kg_paths: List[KGPath] = Field(default_factory=list, description="知识图谱路径")
    confidence_score: float = Field(..., ge=0, le=1, description="整体置信度")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    disclaimer: str = Field(
        default="⚠️ 本系统仅供信息参考，不能替代专业医生的诊断和治疗建议。如有不适，请及时就医。",
        description="免责声明"
    )
    processing_time_ms: int = Field(..., description="处理时间(毫秒)")
    model_used: str = Field(default="gpt-4", description="使用的模型")

    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "q_123456",
                "answer": "头痛可能由多种原因引起...",
                "answer_source": "knowledge_graph",
                "evidence": [
                    {
                        "source": "PubMed",
                        "source_type": "pubmed",
                        "snippet": "偏头痛是一种常见的原发性头痛...",
                        "pmid": "12345678",
                        "confidence": 0.93,
                        "url": "https://pubmed.ncbi.nlm.nih.gov/12345678"
                    }
                ],
                "confidence_score": 0.89,
                "warnings": [],
                "processing_time_ms": 1234
            }
        }
