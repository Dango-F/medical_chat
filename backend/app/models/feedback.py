"""Feedback models for user annotations"""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class FeedbackType(str, Enum):
    """Feedback type enumeration"""
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    INCORRECT = "incorrect"
    MISSING_INFO = "missing_info"
    OTHER = "other"


class FeedbackRequest(BaseModel):
    """User feedback request"""
    query_id: str = Field(..., description="关联的查询ID")
    feedback_type: FeedbackType = Field(..., description="反馈类型")
    rating: Optional[int] = Field(None, ge=1, le=5, description="评分 1-5")
    comment: Optional[str] = Field(None, max_length=1000, description="文字评论")
    user_id: Optional[str] = Field(None, description="用户ID")
    suggested_answer: Optional[str] = Field(None, description="建议的正确答案")

    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "q_123456",
                "feedback_type": "helpful",
                "rating": 5,
                "comment": "回答很准确，参考来源也很有帮助"
            }
        }


class FeedbackResponse(BaseModel):
    """Feedback submission response"""
    feedback_id: str = Field(..., description="反馈ID")
    status: str = Field(default="received", description="状态")
    message: str = Field(default="感谢您的反馈！", description="响应消息")
    created_at: datetime = Field(default_factory=datetime.utcnow)

