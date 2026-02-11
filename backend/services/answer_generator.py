"""答案生成器模块"""
import re
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime

# 导入相关模块
import sys
import os
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_path)

from services.context_manager import ContextManager
from services.document_retriever import RAGRetriever, RetrievedDocument

logger = logging.getLogger(__name__)

class AnswerConfidence(Enum):
    """答案置信度枚举"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"

@dataclass
class GeneratedAnswer:
    """生成的答案"""
    answer: str
    confidence: AnswerConfidence
    confidence_score: float
    sources: List[Dict[str, Any]]
    reasoning: str
    generation_time: float
    metadata: Dict[str, Any]

class PromptBuilder:
    """Prompt构建器"""
    
    def __init__(self):
        """初始化Prompt构建器"""
        self.system_prompt = """你是一个专业的知识问答助手。请根据提供的文档内容回答用户问题。
要求：
1. 基于文档内容准确回答，不要编造信息
2. 如果文档中没有相关信息，请明确说明
3. 回答要简洁明了，重点突出
4. 适当引用文档中的具体内容"""
    
    def build_rag_prompt(self, question: str, context: str, 
                        conversation_history: List[Dict[str, str]] = None) -> str:
        """
        构建RAG问答Prompt
        
        Args:
            question: 用户问题
            context: 检索到的文档上下文
            conversation_history: 对话历史
            
        Returns:
            构建的Prompt字符串
        """
        prompt_parts = []
        
        # 系统指令
        prompt_parts.append(self.system_prompt)
        
        # 对话历史（如果有）
        if conversation_history:
            prompt_parts.append("\n对话历史:")
            for turn in conversation_history[-3:]:  # 只保留最近3轮对话
                role = "用户" if turn['role'] == 'user' else "助手"
                prompt_parts.append(f"{role}: {turn['content']}")
        
        # 文档上下文
        if context:
            prompt_parts.append(f"\n相关文档内容:\n{context}")
        else:
            prompt_parts.append("\n注意：未找到相关文档内容")
        
        # 用户问题
        prompt_parts.append(f"\n用户问题: {question}")
        prompt_parts.append("\n请根据以上文档内容回答问题:")
        
        return "\n".join(prompt_parts)
    
    def build_follow_up_prompt(self, question: str, previous_answer: str,
                              context: str = None) -> str:
        """构建追问Prompt"""
        prompt_parts = []
        
        prompt_parts.append(self.system_prompt)
        prompt_parts.append(f"\n之前的回答: {previous_answer}")
        
        if context:
            prompt_parts.append(f"\n补充文档内容:\n{context}")
        
        prompt_parts.append(f"\n用户追问: {question}")
        prompt_parts.append("\n请基于之前的回答和新信息进行回复:")
        
        return "\n".join(prompt_parts)

class AnswerGenerator:
    """答案生成器"""
    
    def __init__(self, prompt_builder: PromptBuilder = None,
                 context_manager: ContextManager = None):
        """
        初始化答案生成器
        
        Args:
            prompt_builder: Prompt构建器
            context_manager: 上下文管理器
        """
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.context_manager = context_manager
        self.default_confidence_thresholds = {
            AnswerConfidence.HIGH: 0.8,
            AnswerConfidence.MEDIUM: 0.6,
            AnswerConfidence.LOW: 0.4,
            AnswerConfidence.UNCERTAIN: 0.0
        }
    
    def generate_answer(self, question: str, 
                       retrieved_context: Dict[str, Any],
                       conversation_context: Dict[str, Any] = None) -> GeneratedAnswer:
        """
        生成答案
        
        Args:
            question: 用户问题
            retrieved_context: 检索到的上下文
            conversation_context: 对话上下文
            
        Returns:
            生成的答案对象
        """
        start_time = datetime.now()
        
        try:
            # 1. 构建Prompt
            prompt = self._build_prompt(question, retrieved_context, conversation_context)
            
            # 2. 生成答案（模拟实现）
            answer_text, confidence_info = self._generate_answer_text(prompt, retrieved_context)
            
            # 3. 分析置信度
            confidence, confidence_score = self._analyze_confidence(confidence_info, retrieved_context)
            
            # 4. 提取来源信息
            sources = self._extract_sources(retrieved_context)
            
            # 5. 生成推理过程
            reasoning = self._generate_reasoning(question, retrieved_context, answer_text)
            
            # 6. 计算生成时间
            generation_time = (datetime.now() - start_time).total_seconds()
            
            # 7. 构建元数据
            metadata = {
                "question_length": len(question),
                "context_length": len(retrieved_context.get('context', '')),
                "document_count": retrieved_context.get('document_count', 0),
                "generation_method": "rag_based"
            }
            
            answer = GeneratedAnswer(
                answer=answer_text,
                confidence=confidence,
                confidence_score=confidence_score,
                sources=sources,
                reasoning=reasoning,
                generation_time=generation_time,
                metadata=metadata
            )
            
            logger.info(f"答案生成完成: 置信度 {confidence.value} ({confidence_score:.2f})")
            return answer
            
        except Exception as e:
            logger.error(f"答案生成失败: {e}")
            return self._generate_error_answer(str(e))
    
    def _build_prompt(self, question: str, retrieved_context: Dict[str, Any],
                     conversation_context: Dict[str, Any] = None) -> str:
        """构建Prompt"""
        context_text = retrieved_context.get('context', '')
        conversation_history = conversation_context.get('history', []) if conversation_context else []
        
        return self.prompt_builder.build_rag_prompt(
            question=question,
            context=context_text,
            conversation_history=conversation_history
        )
    
    def _generate_answer_text(self, prompt: str, 
                            retrieved_context: Dict[str, Any]) -> tuple:
        """生成答案文本（模拟实现）"""
        context_text = retrieved_context.get('context', '')
        question = prompt.split('用户问题:')[-1].strip()
        
        # 简单的基于规则的答案生成
        if not context_text:
            return "抱歉，我没有找到相关的文档内容来回答您的问题。", {"type": "no_context"}
        
        # 基于关键词匹配的简单回答生成
        answer = self._rule_based_answer_generation(question, context_text)
        
        # 生成置信度信息
        confidence_info = {
            "type": "rule_based",
            "context_match_score": self._calculate_context_match(question, context_text),
            "answer_completeness": len(answer) / max(1, len(question))
        }
        
        return answer, confidence_info
    
    def _rule_based_answer_generation(self, question: str, context: str) -> str:
        """基于规则的答案生成"""
        question_lower = question.lower()
        context_lower = context.lower()
        
        # 简单的关键词匹配和回答模板
        if '什么是' in question_lower or 'what is' in question_lower:
            # 定义类问题
            sentences = re.split(r'[。！？.!?]', context)
            for sentence in sentences:
                if len(sentence.strip()) > 10:  # 找到第一个较长的句子
                    return f"根据文档内容，{sentence.strip()}。"
        
        elif '如何' in question_lower or 'how to' in question_lower:
            # 方法类问题
            if '步骤' in context_lower or 'step' in context_lower:
                return "根据文档内容，相关步骤如下：" + context[:200] + "..."
            else:
                return "文档中提到了相关内容：" + context[:150] + "..."
        
        elif '为什么' in question_lower or 'why' in question_lower:
            # 原因类问题
            return "根据文档分析，主要原因包括：" + context[:180] + "..."
        
        else:
            # 一般问题
            return "根据相关文档内容：" + context[:200] + "..."
    
    def _calculate_context_match(self, question: str, context: str) -> float:
        """计算问题与上下文的匹配度"""
        question_words = set(re.findall(r'[\w\u4e00-\u9fff]+', question.lower()))
        context_words = set(re.findall(r'[\w\u4e00-\u9fff]+', context.lower()))
        
        if not question_words:
            return 0.0
        
        match_count = len(question_words.intersection(context_words))
        return match_count / len(question_words)
    
    def _analyze_confidence(self, confidence_info: Dict[str, Any], 
                          retrieved_context: Dict[str, Any]) -> tuple:
        """分析答案置信度"""
        context_match_score = confidence_info.get('context_match_score', 0)
        answer_completeness = confidence_info.get('answer_completeness', 0)
        
        # 综合置信度计算
        base_score = (context_match_score * 0.6 + answer_completeness * 0.4)
        
        # 考虑文档数量影响
        doc_count = retrieved_context.get('document_count', 0)
        if doc_count == 0:
            base_score *= 0.3  # 没有文档支持，置信度很低
        elif doc_count == 1:
            base_score *= 0.8  # 单个文档支持
        # 多个文档支持保持原分数
        
        # 映射到置信度等级
        if base_score >= self.default_confidence_thresholds[AnswerConfidence.HIGH]:
            confidence = AnswerConfidence.HIGH
        elif base_score >= self.default_confidence_thresholds[AnswerConfidence.MEDIUM]:
            confidence = AnswerConfidence.MEDIUM
        elif base_score >= self.default_confidence_thresholds[AnswerConfidence.LOW]:
            confidence = AnswerConfidence.LOW
        else:
            confidence = AnswerConfidence.UNCERTAIN
        
        return confidence, base_score
    
    def _extract_sources(self, retrieved_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取来源信息"""
        sources = []
        retrieved_docs = retrieved_context.get('retrieved_documents', [])
        
        for doc_info in retrieved_docs:
            source = {
                "document_id": doc_info.get('document_id'),
                "chunk_id": doc_info.get('chunk_id'),
                "score": doc_info.get('score', 0),
                "retrieval_method": doc_info.get('retrieval_method', 'unknown')
            }
            sources.append(source)
        
        return sources
    
    def _generate_reasoning(self, question: str, retrieved_context: Dict[str, Any], 
                          answer: str) -> str:
        """生成推理过程"""
        doc_count = retrieved_context.get('document_count', 0)
        context_length = len(retrieved_context.get('context', ''))
        
        if doc_count == 0:
            return "未找到相关文档内容，无法基于文档回答问题。"
        elif doc_count == 1:
            return f"基于1个相关文档片段（共{context_length}字符）生成回答。"
        else:
            return f"综合{doc_count}个相关文档片段（共{context_length}字符）生成回答。"
    
    def _generate_error_answer(self, error_message: str) -> GeneratedAnswer:
        """生成错误答案"""
        return GeneratedAnswer(
            answer=f"抱歉，回答生成过程中出现错误：{error_message}",
            confidence=AnswerConfidence.UNCERTAIN,
            confidence_score=0.0,
            sources=[],
            reasoning="系统错误导致无法生成有效答案",
            generation_time=0.0,
            metadata={"error": error_message}
        )
    
    def get_generator_stats(self) -> Dict[str, Any]:
        """获取生成器统计信息"""
        return {
            "supported_confidence_levels": [level.value for level in AnswerConfidence],
            "default_confidence_thresholds": {
                level.name.lower(): threshold 
                for level, threshold in self.default_confidence_thresholds.items()
            },
            "generation_methods": ["rag_based", "rule_based"],
            "prompt_builder_available": self.prompt_builder is not None
        }

class ConfidenceAnalyzer:
    """置信度分析器"""
    
    def __init__(self):
        """初始化置信度分析器"""
        pass
    
    def analyze_answer_quality(self, answer: GeneratedAnswer) -> Dict[str, Any]:
        """分析答案质量"""
        quality_metrics = {
            "length_appropriate": self._check_length_appropriateness(answer.answer),
            "contains_citations": self._check_citations(answer.sources),
            "confidence_consistency": self._check_confidence_consistency(answer),
            "overall_quality_score": self._calculate_overall_quality(answer)
        }
        
        return quality_metrics
    
    def _check_length_appropriateness(self, answer_text: str) -> bool:
        """检查答案长度是否合适"""
        length = len(answer_text)
        return 50 <= length <= 500  # 合理的答案长度范围
    
    def _check_citations(self, sources: List[Dict[str, Any]]) -> bool:
        """检查是否包含引用"""
        return len(sources) > 0
    
    def _check_confidence_consistency(self, answer: GeneratedAnswer) -> bool:
        """检查置信度一致性"""
        # 简单的一致性检查
        if answer.confidence == AnswerConfidence.UNCERTAIN and answer.sources:
            return False
        if answer.confidence != AnswerConfidence.UNCERTAIN and not answer.sources:
            return False
        return True
    
    def _calculate_overall_quality(self, answer: GeneratedAnswer) -> float:
        """计算整体质量分数"""
        metrics = self.analyze_answer_quality(answer)
        score_components = [
            float(metrics['length_appropriate']),
            float(metrics['contains_citations']),
            float(metrics['confidence_consistency'])
        ]
        return sum(score_components) / len(score_components)

# 导出主要类
__all__ = ['AnswerConfidence', 'GeneratedAnswer', 'PromptBuilder', 'AnswerGenerator', 'ConfidenceAnalyzer']