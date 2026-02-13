# OpenGuardrails 数据保护集成方案

## 背景

AskMe 知识库系统在 RAG（检索增强生成）环节会调用外部 LLM 生成答案，可能涉及敏感数据泄露风险。OpenGuardrails 是一个开源 AI 安全网关，可自动检测并保护敏感数据。

## 保护范围

| 环节 | 是否调用LLM | 是否需要保护 |
|------|-------------|--------------|
| 文档上传解析 | 否（本地处理） | 不需要 |
| 向量化存储 | 否（本地模型） | 不需要 |
| 语义搜索 | 否（Milvus检索） | 不需要 |
| RAG答案生成 | 是 | **需要** |

只有 RAG 答案生成环节会将用户查询和检索结果发送到外部 LLM，这是唯一需要数据保护的环节。

---

## 方案4：独立网关服务 + 配置切换

### 架构图

```
                              ┌─────────────────────────┐
                              │   OpenGuardrails网关    │
                              │   (localhost:5002)      │
                              │                         │
用户请求 → AskMe后端 ────────→│  检测 → 掩码 → 转发     │──→ 通义千问
    │                        │  ←响应 → 恢复           │──→ 智谱GLM
    │                        └─────────────────────────┘──→ DeepSeek
    │                                    │
    │                                    ↓
    │                        （敏感数据从未离开网关）
    │
    └──────────────────────────────────→ Ollama本地
                            （本地LLM直连，不经过网关）
```

### 核心思路

1. **云端LLM**：所有请求通过 OpenGuardrails 网关转发
2. **本地LLM**：直接连接，不经过网关
3. **配置驱动**：在系统设置中可开启/关闭保护

### 网关部署

#### docker-compose.yml 新增服务

```yaml
services:
  # 现有Milvus服务...
  
  # 新增OpenGuardrails网关
  guardrails:
    image: openguardrails/gateway:latest
    container_name: askme-guardrails
    ports:
      - "5002:5002"
    environment:
      - LOG_LEVEL=info
    volumes:
      - ./config/guardrails.yaml:/app/config.yaml
    restart: unless-stopped
```

#### config/guardrails.yaml 配置

```yaml
# 敏感数据检测策略
detection:
  # PII检测
  - type: email
    action: mask
  - type: phone_number
    action: mask
  - type: credit_card
    action: mask
  - type: id_number
    action: mask
  
  # 凭证检测
  - type: api_key
    action: mask
  - type: password
    action: mask
  - type: database_connection_string
    action: mask
  
  # 自定义关键词
  - type: custom
    keywords:
      - "机密"
      - "内部"
      - "保密"
    action: mask

# 风险等级与响应策略
risk_policy:
  high_risk:
    entities: [api_key, password, database_connection_string]
    action: block  # 或 switch_private_model
  medium_risk:
    entities: [email, phone_number]
    action: mask

# 上游LLM提供商配置
upstream:
  qwen:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  glm:
    base_url: https://open.bigmodel.cn/api/paas/v4
  deepseek:
    base_url: https://api.deepseek.com/v1
  openai:
    base_url: https://api.openai.com/v1
```

### 后端改动

#### llm_service.py 改动逻辑

```python
class BaseLLMProvider:
    def get_actual_api_url(self) -> str:
        """获取实际API地址（可能经过网关）"""
        if self._should_use_guardrail():
            return self._get_guardrail_url()
        return self.config.api_url
    
    def _should_use_guardrail(self) -> bool:
        """判断是否需要走网关"""
        # 条件1：系统开启了保护
        # 条件2：不是本地Ollama
        guardrail_enabled = get_guardrail_config().enabled
        is_local = self.config.provider == "ollama"
        return guardrail_enabled and not is_local
    
    def _get_guardrail_url(self) -> str:
        """返回网关地址，带上提供商标识"""
        return f"http://localhost:5002/v1/{self.config.provider}"
```

#### 新增配置API

```python
# backend/routes/llm_api.py

@router.get("/guardrail/config")
async def get_guardrail_config():
    """获取数据保护配置"""
    return {
        "enabled": settings.guardrail_enabled,
        "gateway_url": settings.guardrail_gateway_url,
        "mode": settings.guardrail_mode  # off/mask/block
    }

@router.post("/guardrail/config")
async def update_guardrail_config(config: GuardrailConfigRequest):
    """更新数据保护配置"""
    settings.guardrail_enabled = config.enabled
    settings.guardrail_mode = config.mode
    return {"success": True}
```

### 前端改动

#### 系统设置新增"数据保护"配置页

| 配置项 | 类型 | 说明 |
|--------|------|------|
| 启用数据保护 | 开关 | 开启后云端LLM请求经过网关 |
| 保护模式 | 单选 | 关闭/掩码/拦截 |
| 网关地址 | 文本 | 默认 http://localhost:5002 |

#### 设置界面示意

```
┌─────────────────────────────────────┐
│ 数据保护设置                         │
├─────────────────────────────────────┤
│                                     │
│  启用数据保护    [=====开关=====]    │
│                                     │
│  保护模式        ○ 关闭              │
│                 ● 掩码（推荐）       │
│                 ○ 拦截              │
│                                     │
│  网关地址        [localhost:5002]   │
│                                     │
│  说明：                             │
│  - 本地Ollama不经过网关，无性能损耗  │
│  - 云端LLM自动检测并保护敏感数据     │
│                                     │
└─────────────────────────────────────┘
```

### 请求流程对比

**场景1：使用本地Ollama**
```
AskMe后端 ────────直连────────→ Ollama (localhost:11434)
          不经过网关，无延迟
```

**场景2：使用通义千问 + 保护开启**
```
AskMe后端 → OpenGuardrails网关 → 通义千问API
              ↓
         检测掩码敏感数据
         响应恢复原始值
```

**场景3：使用通义千问 + 保护关闭**
```
AskMe后端 ────直连────→ 通义千问API
          不经过网关
```

---

## 方案5：仅RAG答案生成环节SDK集成

### 架构图

```
用户搜索请求
     ↓
向量检索（本地Milvus）
     ↓
检索结果 + 用户查询
     ↓
┌─────────────────────────────────────┐
│     判断LLM类型                      │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ 本地Ollama  │  │ 云端LLM      │  │
│  │   直连      │  │ OpenGuardrails│  │
│  └─────────────┘  │   掩码→发送   │  │
│        ↓          │   ←恢复       │  │
│     返回答案      └──────────────┘  │
└─────────────────────────────────────┘
```

### 改动范围

**文件**：`backend/services/llm_service.py`

**改动逻辑**：
1. 新增 `GuardrailService` 类，封装 OpenGuardrails SDK
2. 在 `RAGGenerator` 中，根据 Provider 类型决定是否启用保护
3. 云端 Provider 调用时：先掩码 → 调用LLM → 恢复敏感数据
4. 本地 Ollama 调用时：直接调用，不经过保护层

### 依赖安装

```bash
pip install openguardrails
```

### 核心代码设计

#### backend/services/guardrail_service.py

```python
from openguardrails import OpenGuardrails
from typing import Tuple, Dict, Any

class GuardrailService:
    """OpenGuardrails数据保护服务"""
    
    def __init__(self, api_key: str = None, enabled: bool = True):
        """
        初始化保护服务
        
        Args:
            api_key: OpenGuardrails API Key（云端模式）
            enabled: 是否启用保护
        """
        self.enabled = enabled
        self.client = OpenGuardrails(api_key) if api_key else None
        self._mapping: Dict[str, Any] = {}
    
    def protect_prompt(self, prompt: str) -> Tuple[str, Dict]:
        """
        检测并掩码敏感数据
        
        Args:
            prompt: 原始prompt
            
        Returns:
            (掩码后的prompt, 掩码映射表)
        """
        if not self.enabled or not self.client:
            return prompt, {}
        
        result = self.client.check_prompt(prompt)
        
        if result.suggest_action == "anonymize":
            masked_prompt = self.client.anonymize(prompt)
            self._mapping = result.detected_entities
            return masked_prompt, self._mapping
        
        return prompt, {}
    
    def restore_response(self, response: str, mapping: Dict = None) -> str:
        """
        恢复掩码的敏感数据
        
        Args:
            response: LLM返回的响应（包含掩码占位符）
            mapping: 掩码映射表
            
        Returns:
            恢复后的响应
        """
        if not self.enabled or not self.client:
            return response
        
        mapping = mapping or self._mapping
        if not mapping:
            return response
        
        return self.client.deanonymize(response, mapping)
    
    def check_risk(self, prompt: str) -> str:
        """
        检查风险等级
        
        Returns:
            'low' / 'medium' / 'high'
        """
        if not self.client:
            return 'low'
        
        result = self.client.check_prompt(prompt)
        return result.risk_level or 'low'
```

#### backend/services/llm_service.py 修改

```python
from services.guardrail_service import GuardrailService

class RAGGenerator:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider = self._create_provider(config)
        
        # 初始化数据保护服务
        self.guardrail = GuardrailService(
            api_key=config.guardrail_api_key,
            enabled=config.enable_guardrail
        )
    
    async def generate_answer(self, query: str, contexts: list[str]) -> str:
        """生成RAG答案"""
        # 构建完整prompt
        full_prompt = self._build_prompt(query, contexts)
        
        # 判断是否需要保护（仅云端LLM）
        if self._needs_protection():
            # 掩码
            masked_prompt, mapping = self.guardrail.protect_prompt(full_prompt)
            
            # 调用LLM
            response = await self.provider.generate(masked_prompt)
            
            # 恢复
            return self.guardrail.restore_response(response, mapping)
        else:
            # 本地Ollama直接调用
            return await self.provider.generate(full_prompt)
    
    def _needs_protection(self) -> bool:
        """判断是否需要数据保护"""
        # 本地Ollama不需要保护
        return self.config.enable_guardrail and self.config.provider not in ["ollama", "local"]
    
    def _build_prompt(self, query: str, contexts: list[str]) -> str:
        """构建RAG prompt"""
        context_text = "\n\n".join(contexts)
        return f"""基于以下参考信息回答问题。如果参考信息中没有相关内容，请说明。

参考信息：
{context_text}

问题：{query}

请给出准确、简洁的回答："""
```

### 配置项设计

在系统设置中新增：

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `enable_guardrail` | bool | 是否启用数据保护 |
| `guardrail_api_key` | string | OpenGuardrails API Key（可选，本地部署可不用） |
| `guardrail_mode` | enum | `off` / `mask` / `block` |

### 部署方式

#### 选项A：使用云服务（需要API Key）

```python
guardrail = GuardrailService(api_key="your-api-key", enabled=True)
```

#### 选项B：本地部署（完全离线）

```bash
# docker-compose.yml 新增服务
services:
  guardrails:
    image: openguardrails/gateway:latest
    ports:
      - "5002:5002"
```

```python
# 本地部署无需API Key
guardrail = GuardrailService(enabled=True)  # 本地模式
```

---

## 方案对比

| 维度 | 方案4（独立网关） | 方案5（SDK集成） |
|------|-------------------|------------------|
| 代码改动量 | 少（仅配置） | 中（改llm_service） |
| 部署复杂度 | 高（多一个服务） | 低（仅装依赖） |
| 策略管理 | 网关统一配置 | 代码中配置 |
| 性能影响 | 网络多一跳 | 本地处理 |
| 运维成本 | 高（监控网关） | 低 |
| 灵活性 | 高（热更新策略） | 低（需重启） |
| 适用场景 | 企业级部署 | 快速集成 |

---

## 建议

根据项目特点，建议：

1. **快速验证阶段**：采用方案5（SDK集成），改动小、见效快
2. **生产部署阶段**：可迁移至方案4（独立网关），便于统一管理和策略热更新
