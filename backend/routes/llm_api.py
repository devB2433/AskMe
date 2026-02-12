"""LLM配置和问答API"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from services.llm_service import (
    LLMConfig, LLMService, RAGGenerator,
    get_llm_service, get_rag_generator, save_llm_config
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["llm"])


# ========== 配置相关 ==========

class LLMConfigRequest(BaseModel):
    """LLM配置请求"""
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    api_url: str = "http://localhost:11434"
    api_key: str = ""
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 60


class LLMConfigResponse(BaseModel):
    """LLM配置响应"""
    provider: str
    model: str
    api_url: str
    api_key_masked: str
    max_tokens: int
    temperature: float
    timeout: int
    available_presets: List[Dict[str, str]]


@router.get("/config", summary="获取LLM配置")
async def get_llm_config_api():
    """获取当前LLM配置"""
    llm = get_llm_service()
    config = llm.config
    
    # 获取预设列表
    presets = []
    for key, preset in LLMService.PRESETS.items():
        presets.append({
            "key": key,
            "provider": preset.provider,
            "model": preset.model,
            "name": _get_preset_name(key)
        })
    
    return {
        "provider": config.provider,
        "model": config.model,
        "api_url": config.api_url,
        "api_key_masked": _mask_api_key(config.api_key),
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "timeout": config.timeout,
        "available_presets": presets
    }


@router.post("/config", summary="保存LLM配置")
async def save_llm_config_api(config: LLMConfigRequest):
    """保存LLM配置"""
    new_config = LLMConfig(
        provider=config.provider,
        model=config.model,
        api_url=config.api_url,
        api_key=config.api_key,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        timeout=config.timeout
    )
    
    save_llm_config(new_config)
    
    return {"message": "配置保存成功", "provider": config.provider, "model": config.model}


@router.post("/config/preset/{preset_key}", summary="应用预设配置")
async def apply_preset_config(preset_key: str):
    """应用预设配置"""
    if preset_key not in LLMService.PRESETS:
        raise HTTPException(status_code=404, detail=f"预设 '{preset_key}' 不存在")
    
    preset = LLMService.PRESETS[preset_key]
    save_llm_config(preset)
    
    return {
        "message": f"已应用预设: {_get_preset_name(preset_key)}",
        "provider": preset.provider,
        "model": preset.model
    }


@router.get("/test", summary="测试LLM连接")
async def test_llm_connection():
    """测试LLM连接"""
    try:
        llm = get_llm_service()
        answer = await llm.generate("你好，请回复'连接成功'", "你是一个测试助手")
        return {"status": "success", "response": answer[:100]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========== 问答相关 ==========

class QuestionRequest(BaseModel):
    """问答请求"""
    question: str
    contexts: Optional[List[Dict[str, Any]]] = None
    max_contexts: int = 5


class QuestionResponse(BaseModel):
    """问答响应"""
    question: str
    answer: str
    sources: List[Dict[str, Any]]


@router.post("/ask", summary="基于上下文生成回答")
async def ask_question(request: QuestionRequest):
    """基于提供的上下文生成回答"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    
    if not request.contexts:
        return {
            "question": request.question,
            "answer": "抱歉，没有提供参考资料，无法回答问题。",
            "sources": []
        }
    
    try:
        rag = get_rag_generator()
        answer = await rag.generate_answer(
            query=request.question,
            contexts=request.contexts,
            max_contexts=request.max_contexts
        )
        
        return {
            "question": request.question,
            "answer": answer,
            "sources": request.contexts[:request.max_contexts]
        }
    except Exception as e:
        logger.error(f"生成回答失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成回答失败: {str(e)}")


# ========== 辅助函数 ==========

def _mask_api_key(api_key: str) -> str:
    """隐藏API密钥"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return api_key[:4] + "****" + api_key[-4:]


def _get_preset_name(preset_key: str) -> str:
    """获取预设显示名称"""
    names = {
        "ollama_qwen": "Ollama - Qwen2.5 7B (本地)",
        "ollama_llama": "Ollama - Llama3.1 8B (本地)",
        "qwen_plus": "通义千问 Plus (云端)",
        "qwen_turbo": "通义千问 Turbo (云端)",
        "glm_4": "智谱GLM-4 (云端)",
        "glm_4_flash": "智谱GLM-4-Flash (云端)",
        "deepseek": "DeepSeek Chat (云端)"
    }
    return names.get(preset_key, preset_key)
