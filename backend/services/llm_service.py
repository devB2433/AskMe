"""大语言模型服务模块 - 支持Ollama/通义千问/OpenAI兼容API"""
import httpx
import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from abc import ABC, abstractmethod
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """大模型配置"""
    provider: str = "ollama"  # ollama, qwen, openai, custom
    model: str = "qwen2.5:7b"  # 模型名称
    api_url: str = "http://localhost:11434"  # API地址
    api_key: str = ""  # API密钥
    max_tokens: int = 2048  # 最大输出token
    temperature: float = 0.7  # 温度
    timeout: int = 60  # 超时时间（秒）


class BaseLLMProvider(ABC):
    """LLM提供者基类"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """生成回答"""
        pass
    
    @abstractmethod
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
        """流式生成回答"""
        pass


class OllamaProvider(BaseLLMProvider):
    """Ollama本地模型提供者"""
    
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """生成回答"""
        url = f"{self.config.api_url}/api/generate"
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "num_predict": self.config.max_tokens,
                "temperature": self.config.temperature
            }
        }
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
    
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
        """流式生成回答"""
        url = f"{self.config.api_url}/api/generate"
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": True,
            "options": {
                "num_predict": self.config.max_tokens,
                "temperature": self.config.temperature
            }
        }
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI兼容API提供者（支持通义千问、DeepSeek等）"""
    
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """生成回答"""
        url = f"{self.config.api_url}/v1/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False
        }
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
        """流式生成回答"""
        url = f"{self.config.api_url}/v1/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue


class QwenProvider(OpenAICompatibleProvider):
    """通义千问API提供者"""
    
    def __init__(self, config: LLMConfig):
        # 通义千问API地址
        if not config.api_url or config.api_url == "http://localhost:11434":
            config.api_url = "https://dashscope.aliyuncs.com/compatible-mode"
        if not config.model:
            config.model = "qwen-plus"
        super().__init__(config)


class GLMProvider(BaseLLMProvider):
    """智谱GLM API提供者"""
    
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """生成回答"""
        url = f"{self.config.api_url}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False
        }
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
        """流式生成回答"""
        url = f"{self.config.api_url}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True
        }
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue


class LLMService:
    """大语言模型服务"""
    
    # 默认配置
    DEFAULT_CONFIG = LLMConfig()
    
    # 预设配置
    PRESETS = {
        "ollama_qwen": LLMConfig(
            provider="ollama",
            model="qwen2.5:7b",
            api_url="http://localhost:11434"
        ),
        "ollama_llama": LLMConfig(
            provider="ollama",
            model="llama3.1:8b",
            api_url="http://localhost:11434"
        ),
        "qwen_plus": LLMConfig(
            provider="qwen",
            model="qwen-plus",
            api_url="https://dashscope.aliyuncs.com/compatible-mode"
        ),
        "qwen_turbo": LLMConfig(
            provider="qwen",
            model="qwen-turbo",
            api_url="https://dashscope.aliyuncs.com/compatible-mode"
        ),
        "glm_4": LLMConfig(
            provider="glm",
            model="glm-4",
            api_url="https://open.bigmodel.cn/api/paas/v4"
        ),
        "glm_4_flash": LLMConfig(
            provider="glm",
            model="glm-4-flash",
            api_url="https://open.bigmodel.cn/api/paas/v4"
        ),
        "deepseek": LLMConfig(
            provider="openai",
            model="deepseek-chat",
            api_url="https://api.deepseek.com"
        ),
    }
    
    def __init__(self, config: LLMConfig = None):
        self.config = config or self.DEFAULT_CONFIG
        self._provider = None
    
    def _get_provider(self) -> BaseLLMProvider:
        """获取LLM提供者"""
        if self._provider is None:
            provider = self.config.provider.lower()
            if provider == "ollama":
                self._provider = OllamaProvider(self.config)
            elif provider == "qwen":
                self._provider = QwenProvider(self.config)
            elif provider == "glm":
                self._provider = GLMProvider(self.config)
            else:
                self._provider = OpenAICompatibleProvider(self.config)
        return self._provider
    
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """生成回答"""
        provider = self._get_provider()
        return await provider.generate(prompt, system_prompt)
    
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
        """流式生成回答"""
        provider = self._get_provider()
        async for chunk in provider.generate_stream(prompt, system_prompt):
            yield chunk
    
    def update_config(self, config: LLMConfig):
        """更新配置"""
        self.config = config
        self._provider = None  # 重置provider


class RAGGenerator:
    """RAG生成器 - 整合检索结果生成回答"""
    
    # 系统提示词模板
    SYSTEM_PROMPT = """你是一个专业的知识库问答助手。你的任务是根据提供的参考资料，准确、专业地回答用户的问题。

请注意以下要求：
1. 只使用参考资料中的信息回答问题，不要编造内容
2. 如果参考资料中没有相关信息，请明确告知用户
3. 回答要简洁明了，重点突出
4. 如果引用了具体内容，请注明来源文档
5. 使用中文回答"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """用户问题：{query}

参考资料：
{contexts}

请根据以上参考资料，回答用户的问题。如果参考资料中没有相关信息，请说明。"""

    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()
    
    def build_prompt(self, query: str, contexts: List[Dict[str, Any]]) -> str:
        """构建提示词"""
        # 格式化上下文
        context_strs = []
        for i, ctx in enumerate(contexts, 1):
            filename = ctx.get("filename", "未知文档")
            content = ctx.get("content", ctx.get("matches", [""])[0] if ctx.get("matches") else "")
            context_strs.append(f"[文档{i}] {filename}\n{content}")
        
        contexts_str = "\n\n".join(context_strs)
        
        return self.USER_PROMPT_TEMPLATE.format(
            query=query,
            contexts=contexts_str
        )
    
    async def generate_answer(
        self, 
        query: str, 
        contexts: List[Dict[str, Any]],
        max_contexts: int = 5
    ) -> str:
        """生成回答"""
        # 限制上下文数量
        contexts = contexts[:max_contexts]
        
        if not contexts:
            return "抱歉，没有找到相关的参考资料来回答您的问题。"
        
        prompt = self.build_prompt(query, contexts)
        
        try:
            answer = await self.llm_service.generate(prompt, self.SYSTEM_PROMPT)
            return answer
        except Exception as e:
            logger.error(f"生成回答失败: {e}")
            return f"生成回答时出现错误: {str(e)}"
    
    async def generate_answer_stream(
        self, 
        query: str, 
        contexts: List[Dict[str, Any]],
        max_contexts: int = 5
    ) -> AsyncGenerator[str, None]:
        """流式生成回答"""
        contexts = contexts[:max_contexts]
        
        if not contexts:
            yield "抱歉，没有找到相关的参考资料来回答您的问题。"
            return
        
        prompt = self.build_prompt(query, contexts)
        
        try:
            async for chunk in self.llm_service.generate_stream(prompt, self.SYSTEM_PROMPT):
                yield chunk
        except Exception as e:
            logger.error(f"流式生成回答失败: {e}")
            yield f"\n[错误] {str(e)}"


# 全局实例
_llm_service_instance = None
_rag_generator_instance = None


def get_llm_service() -> LLMService:
    """获取LLM服务实例"""
    global _llm_service_instance
    if _llm_service_instance is None:
        # 从配置加载
        config = _load_llm_config()
        _llm_service_instance = LLMService(config)
    return _llm_service_instance


def get_rag_generator() -> RAGGenerator:
    """获取RAG生成器实例"""
    global _rag_generator_instance
    if _rag_generator_instance is None:
        _rag_generator_instance = RAGGenerator(get_llm_service())
    return _rag_generator_instance


def _load_llm_config() -> LLMConfig:
    """从配置文件加载LLM配置"""
    import json
    from pathlib import Path
    
    config_path = Path("data/llm_config.json")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return LLMConfig(
                provider=data.get("provider", "ollama"),
                model=data.get("model", "qwen2.5:7b"),
                api_url=data.get("api_url", "http://localhost:11434"),
                api_key=data.get("api_key", ""),
                max_tokens=data.get("max_tokens", 2048),
                temperature=data.get("temperature", 0.7),
                timeout=data.get("timeout", 60)
            )
        except Exception as e:
            logger.warning(f"加载LLM配置失败: {e}")
    
    return LLMConfig()


def save_llm_config(config: LLMConfig):
    """保存LLM配置"""
    import json
    from pathlib import Path
    
    config_path = Path("data/llm_config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "provider": config.provider,
        "model": config.model,
        "api_url": config.api_url,
        "api_key": config.api_key,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "timeout": config.timeout
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 更新全局实例
    global _llm_service_instance
    if _llm_service_instance:
        _llm_service_instance.update_config(config)


# 导出
__all__ = [
    'LLMConfig',
    'LLMService',
    'RAGGenerator',
    'get_llm_service',
    'get_rag_generator',
    'save_llm_config'
]
