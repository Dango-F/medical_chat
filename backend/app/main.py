"""FastAPI Application Entry Point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.core.config import settings
from app.api.v1.router import api_router
from app.services.kg_service import kg_service
from app.services.vector_service import vector_service
from app.services.qa_service import qa_service


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events"""
    # Startup
    logger.info(f"Starting {settings.app_name}...")

    # Initialize services
    try:
        await kg_service.initialize()
        logger.info("Knowledge Graph service initialized")
    except Exception as e:
        logger.warning(f"KG service initialization skipped: {e}")

    try:
        await vector_service.initialize()
        logger.info("Vector search service initialized")
    except Exception as e:
        logger.warning(f"Vector service initialization skipped: {e}")

    try:
        await qa_service.initialize()
        logger.info(f"QA service initialized (LLM provider: {qa_service._llm_provider})")
    except Exception as e:
        logger.warning(f"QA service initialization skipped: {e}")

    logger.info(f"{settings.app_name} started successfully!")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await kg_service.close()
    await vector_service.close()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
## 基于知识图谱的医疗问答系统 API

本系统提供基于知识图谱和大语言模型的医疗问答服务。

### 主要功能

- **自然语言问答**: 支持医疗相关问题的智能问答
- **知识图谱查询**: 查询医疗实体和关系
- **证据溯源**: 所有回答均提供来源引用

### ⚠️ 免责声明

本系统仅供信息参考，不能替代专业医生的诊断和治疗建议。
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - Health check"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "api": "up",
            "kg": kg_service.is_connected,
            "vector": vector_service.is_connected
        }
    }


# 支持直接运行: python -m app.main
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development
    )
