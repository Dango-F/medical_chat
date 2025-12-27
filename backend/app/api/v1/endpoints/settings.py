# coding: utf-8
"""Settings API - LLM Provider Configuration"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from loguru import logger

from app.services.qa_service import qa_service
from app.core.config import settings

router = APIRouter()


class LLMConfig(BaseModel):
    """LLM 配置模型"""
    provider: str  # siliconflow, gemini, openai, mock
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class LLMStatusResponse(BaseModel):
    """LLM 状态响应"""
    current_provider: str
    current_model: str
    is_connected: bool
    available_providers: List[dict]
    has_api_key: dict  # 每个提供商是否有配置的 API Key


class UpdateLLMRequest(BaseModel):
    """更新 LLM 配置请求"""
    provider: str
    api_key: Optional[str] = None  # 可选，如果不提供则使用默认配置
    model: Optional[str] = None
    base_url: Optional[str] = None


class UpdateLLMResponse(BaseModel):
    """更新 LLM 配置响应"""
    success: bool
    message: str
    provider: str
    model: str


# 运行时配置存储（重启后会重置为 .env 配置）
_runtime_config = {
    "provider": None,
    "api_key": None,
    "model": None,
    "base_url": None
}


@router.get("/llm/status", response_model=LLMStatusResponse)
async def get_llm_status():
    """获取当前 LLM 配置状态"""
    provider = qa_service._llm_provider

    # 根据 provider 获取当前模型
    model_map = {
        "mock": "知识图谱直接回答",
        "siliconflow": _runtime_config.get("model") or settings.siliconflow_model,
        "gemini": "gemini-1.5-flash",
        "openai": "gpt-4"
    }

    current_model = model_map.get(provider, "unknown")

    # 可用的提供商列表
    available_providers = [
        {
            "id": "siliconflow",
            "name": "硅基流动 (SiliconFlow)",
            "description": "支持 DeepSeek、Qwen 等模型",
            "models": [
                {"id": "deepseek-ai/DeepSeek-V3.2", "name": "DeepSeek-V3.2 (快速)"},
                {"id": "deepseek-ai/DeepSeek-R1", "name": "DeepSeek-R1 (深度思考)"},
                {"id": "Qwen/Qwen3-VL-32B-Thinking", "name": "Qwen3-VL-32B (思考)"},
                {"id": "Qwen/Qwen3-VL-32B-Instruct", "name": "Qwen3-VL-32B (指令)"},
                {"id": "Qwen/Qwen3-VL-30B-A3B-Thinking", "name": "Qwen3-VL-30B-A3B (思考)"}
            ],
            "base_url": "https://api.siliconflow.cn/v1",
            "requires_key": True
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "description": "Google 的 Gemini 模型",
            "models": [
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}
            ],
            "requires_key": True
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "OpenAI GPT 系列模型",
            "models": [
                {"id": "gpt-4", "name": "GPT-4"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"}
            ],
            "requires_key": True
        },
        {
            "id": "mock",
            "name": "知识图谱模式",
            "description": "直接使用知识图谱数据回答，无需 API Key",
            "models": [
                {"id": "knowledge-graph", "name": "知识图谱直接回答"}
            ],
            "requires_key": False
        }
    ]

    # 检查每个提供商是否有配置的 API Key
    has_api_key = {
        "siliconflow": bool(_runtime_config.get("api_key") or settings.siliconflow_api_key),
        "gemini": bool(_runtime_config.get("api_key") if _runtime_config.get("provider") == "gemini" else settings.gemini_api_key),
        "openai": bool(_runtime_config.get("api_key") if _runtime_config.get("provider") == "openai" else settings.openai_api_key),
        "mock": True  # mock 不需要 API Key
    }

    return LLMStatusResponse(
        current_provider=provider,
        current_model=current_model,
        is_connected=provider != "mock" or qa_service._llm_provider == "mock",
        available_providers=available_providers,
        has_api_key=has_api_key
    )


@router.post("/llm/update", response_model=UpdateLLMResponse)
async def update_llm_config(request: UpdateLLMRequest):
    """更新 LLM 配置（运行时生效，重启后重置）"""
    try:
        provider = request.provider.lower()

        if provider == "mock":
            # 切换到 mock 模式
            qa_service._llm_provider = "mock"
            qa_service.siliconflow_client = None
            qa_service.gemini_model = None
            qa_service.openai_client = None

            _runtime_config["provider"] = "mock"
            _runtime_config["model"] = "knowledge-graph"

            logger.info("Switched to mock mode (Knowledge Graph only)")
            return UpdateLLMResponse(
                success=True,
                message="已切换到知识图谱模式",
                provider="mock",
                model="知识图谱直接回答"
            )

        elif provider == "siliconflow":
            # 使用传入的 API Key 或默认配置
            api_key = request.api_key or _runtime_config.get(
                "api_key") or settings.siliconflow_api_key
            if not api_key:
                raise HTTPException(status_code=400, detail="硅基流动需要提供 API Key")

            from openai import AsyncOpenAI
            base_url = request.base_url or "https://api.siliconflow.cn/v1"
            model = request.model or "deepseek-ai/DeepSeek-V3.2"

            # 测试连接
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)

            # 更新服务
            qa_service.siliconflow_client = client
            qa_service._llm_provider = "siliconflow"

            # 保存运行时配置
            _runtime_config["provider"] = "siliconflow"
            _runtime_config["api_key"] = api_key
            _runtime_config["model"] = model
            _runtime_config["base_url"] = base_url

            # 动态更新 settings（仅运行时有效）
            settings.siliconflow_api_key = api_key
            settings.siliconflow_model = model
            settings.siliconflow_base_url = base_url

            logger.info(f"SiliconFlow client updated (model: {model})")
            return UpdateLLMResponse(
                success=True,
                message=f"已切换到硅基流动 ({model})",
                provider="siliconflow",
                model=model
            )

        elif provider == "gemini":
            # 使用传入的 API Key 或默认配置
            api_key = request.api_key or (_runtime_config.get("api_key") if _runtime_config.get(
                "provider") == "gemini" else None) or settings.gemini_api_key
            if not api_key:
                raise HTTPException(
                    status_code=400, detail="Gemini 需要提供 API Key")

            import google.generativeai as genai
            genai.configure(api_key=api_key)
            qa_service.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            qa_service._llm_provider = "gemini"

            _runtime_config["provider"] = "gemini"
            _runtime_config["api_key"] = api_key
            _runtime_config["model"] = "gemini-1.5-flash"

            logger.info("Gemini client updated")
            return UpdateLLMResponse(
                success=True,
                message="已切换到 Google Gemini",
                provider="gemini",
                model="gemini-1.5-flash"
            )

        elif provider == "openai":
            # 使用传入的 API Key 或默认配置
            api_key = request.api_key or (_runtime_config.get("api_key") if _runtime_config.get(
                "provider") == "openai" else None) or settings.openai_api_key
            if not api_key:
                raise HTTPException(
                    status_code=400, detail="OpenAI 需要提供 API Key")

            from openai import AsyncOpenAI
            qa_service.openai_client = AsyncOpenAI(api_key=api_key)
            qa_service._llm_provider = "openai"

            _runtime_config["provider"] = "openai"
            _runtime_config["api_key"] = api_key
            _runtime_config["model"] = request.model or "gpt-4"

            logger.info("OpenAI client updated")
            return UpdateLLMResponse(
                success=True,
                message="已切换到 OpenAI",
                provider="openai",
                model=request.model or "gpt-4"
            )

        else:
            raise HTTPException(status_code=400, detail=f"不支持的提供商: {provider}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update LLM config: {e}")
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")


@router.post("/llm/test")
async def test_llm_connection(request: UpdateLLMRequest):
    """测试 LLM 连接是否有效"""
    try:
        provider = request.provider.lower()

        if provider == "mock":
            return {"success": True, "message": "知识图谱模式无需测试"}

        elif provider == "siliconflow":
            # 使用传入的 API Key 或默认配置
            api_key = request.api_key or _runtime_config.get(
                "api_key") or settings.siliconflow_api_key
            if not api_key:
                return {"success": False, "message": "请提供 API Key"}

            from openai import AsyncOpenAI
            base_url = request.base_url or "https://api.siliconflow.cn/v1"
            model = request.model or "deepseek-ai/DeepSeek-V3.2"

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "你好"}],
                max_tokens=10
            )
            return {"success": True, "message": "硅基流动连接成功", "response": response.choices[0].message.content}

        elif provider == "gemini":
            # 使用传入的 API Key 或默认配置
            api_key = request.api_key or (_runtime_config.get("api_key") if _runtime_config.get(
                "provider") == "gemini" else None) or settings.gemini_api_key
            if not api_key:
                return {"success": False, "message": "请提供 API Key"}

            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(
                "你好", generation_config={"max_output_tokens": 10})
            return {"success": True, "message": "Gemini 连接成功", "response": response.text}

        elif provider == "openai":
            # 使用传入的 API Key 或默认配置
            api_key = request.api_key or (_runtime_config.get("api_key") if _runtime_config.get(
                "provider") == "openai" else None) or settings.openai_api_key
            if not api_key:
                return {"success": False, "message": "请提供 API Key"}

            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "你好"}],
                max_tokens=10
            )
            return {"success": True, "message": "OpenAI 连接成功", "response": response.choices[0].message.content}

        else:
            return {"success": False, "message": f"不支持的提供商: {provider}"}

    except Exception as e:
        return {"success": False, "message": f"连接测试失败: {str(e)}"}
