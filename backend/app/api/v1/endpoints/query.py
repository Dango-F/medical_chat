"""Query API Endpoint - Main QA Interface"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.query import QueryRequest, QueryResponse
from app.services.qa_service import qa_service

router = APIRouter()


@router.post("", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    处理医疗问答查询
    
    - **query**: 用户的自然语言问题
    - **max_answers**: 返回的最大证据数量 (1-10)
    - **include_kg_paths**: 是否包含知识图谱路径
    - **include_evidence**: 是否包含文献证据
    
    返回结构化的回答，包含：
    - 生成的回答文本
    - 证据列表（包含来源、置信度等）
    - 知识图谱路径
    - 整体置信度评分
    - 医疗免责声明
    """
    try:
        logger.info(f"Received query: {request.query[:100]}...")
        response = await qa_service.process_query(request)
        return response
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"查询处理失败: {str(e)}"
        )


@router.post("/stream")
async def process_query_stream(request: QueryRequest):
    """
    流式处理医疗问答查询（逐步返回结果）
    
    返回 Server-Sent Events (SSE) 格式的流式响应
    LLM回复会一点一点流式输出，而不是等待完整回答
    """
    import json
    
    async def generate():
        try:
            async for chunk in qa_service.process_query_stream(request):
                yield chunk
        except Exception as e:
            logger.error(f"Stream processing failed: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        }
    )


@router.get("/examples")
async def get_example_queries():
    """
    获取示例问题列表
    
    返回10个预设的医疗问题示例，用于演示和测试
    """
    examples = [
        {
            "id": 1,
            "query": "头痛两天了，可能是什么原因？什么情况需要就医？",
            "category": "症状咨询"
        },
        {
            "id": 2,
            "query": "偏头痛和紧张性头痛有什么区别？",
            "category": "疾病鉴别"
        },
        {
            "id": 3,
            "query": "布洛芬的用法用量和注意事项是什么？",
            "category": "用药指导"
        },
        {
            "id": 4,
            "query": "发烧38.5度，需要吃退烧药吗？",
            "category": "症状咨询"
        },
        {
            "id": 5,
            "query": "2型糖尿病的一线治疗药物是什么？",
            "category": "治疗方案"
        },
        {
            "id": 6,
            "query": "高血压患者的血压控制目标是多少？",
            "category": "疾病管理"
        },
        {
            "id": 7,
            "query": "感冒和流感有什么区别？如何治疗？",
            "category": "疾病鉴别"
        },
        {
            "id": 8,
            "query": "头痛伴发热和颈部僵硬是什么情况？",
            "category": "危险信号"
        },
        {
            "id": 9,
            "query": "糖尿病患者需要做哪些定期检查？",
            "category": "健康管理"
        },
        {
            "id": 10,
            "query": "奥司他韦什么时候服用效果最好？",
            "category": "用药指导"
        }
    ]
    return {"examples": examples, "total": len(examples)}

