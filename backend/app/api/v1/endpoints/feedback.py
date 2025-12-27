"""Feedback API Endpoint - User feedback collection"""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter()

# In-memory storage for MVP (would use database in production)
_feedback_store = []


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    提交用户反馈
    
    用于收集用户对回答质量的反馈，支持以下类型：
    - helpful: 回答有帮助
    - not_helpful: 回答没有帮助
    - incorrect: 回答有误
    - missing_info: 缺少关键信息
    - other: 其他反馈
    
    反馈数据将用于改进系统质量。
    """
    try:
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        
        feedback_entry = {
            "feedback_id": feedback_id,
            "query_id": request.query_id,
            "feedback_type": request.feedback_type.value,
            "rating": request.rating,
            "comment": request.comment,
            "user_id": request.user_id,
            "suggested_answer": request.suggested_answer,
            "created_at": datetime.utcnow().isoformat()
        }
        
        _feedback_store.append(feedback_entry)
        logger.info(f"Received feedback {feedback_id} for query {request.query_id}")
        
        return FeedbackResponse(
            feedback_id=feedback_id,
            status="received",
            message="感谢您的反馈！您的意见将帮助我们改进服务。",
            created_at=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Failed to process feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_feedback_stats():
    """
    获取反馈统计（仅供管理员）
    
    返回反馈数量和类型分布
    """
    if not _feedback_store:
        return {
            "total": 0,
            "by_type": {},
            "average_rating": None
        }
    
    by_type = {}
    ratings = []
    
    for fb in _feedback_store:
        fb_type = fb.get("feedback_type", "unknown")
        by_type[fb_type] = by_type.get(fb_type, 0) + 1
        if fb.get("rating"):
            ratings.append(fb["rating"])
    
    return {
        "total": len(_feedback_store),
        "by_type": by_type,
        "average_rating": sum(ratings) / len(ratings) if ratings else None
    }

