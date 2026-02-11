"""查询处理器模块"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import jieba
import jieba.analyse
from collections import defaultdict
import sys
import os

# 添加项目路径以支持相对导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class QueryType(Enum):
    """查询类型枚举"""
    KEYWORD = "keyword"      # 关键词搜索
    SEMANTIC = "semantic"    # 语义搜索
    HYBRID = "hybrid"        # 混合搜索
    FILTER = "filter"        # 过滤查询
    FACET = "facet"          # 分面搜索

@dataclass
class ParsedQuery:
    """解析后的查询对象"""
    original_query: str
    query_type: QueryType
    keywords: List[str]
    semantic_terms: List[str]
    filters: Dict[str, Any]
    facets: List[str]
    boost_factors: Dict[str, float]
    pagination: Dict[str, int]

class QueryParser:
    """查询解析器"""
    
    def __init__(self):
        # 初始化中文分词
        jieba.initialize()
        
        # 定义操作符
        self.operators = {
            'AND': ['AND', '并且', '同时'],
            'OR': ['OR', '或者', '或是'],
            'NOT': ['NOT', '非', '不包含'],
            'FILTER': [':', '=', '是', '等于'],
            'RANGE': ['..', '至', '到']
        }
        
        # 定义字段映射
        self.field_mappings = {
            '标题': 'title',
            '作者': 'author', 
            '时间': 'created_at',
            '类型': 'content_type',
            '语言': 'language',
            '分类': 'category'
        }
    
    def parse(self, query_string: str) -> ParsedQuery:
        """
        解析查询字符串
        
        Args:
            query_string: 原始查询字符串
            
        Returns:
            解析后的查询对象
        """
        if not query_string or not query_string.strip():
            raise ValueError("查询字符串不能为空")
        
        query_string = query_string.strip()
        original_query = query_string
        
        # 识别查询类型
        query_type = self._identify_query_type(query_string)
        
        # 提取关键词
        keywords = self._extract_keywords(query_string)
        
        # 提取语义术语
        semantic_terms = self._extract_semantic_terms(query_string)
        
        # 解析过滤条件
        filters = self._parse_filters(query_string)
        
        # 解析分面字段
        facets = self._parse_facets(query_string)
        
        # 解析权重因子
        boost_factors = self._parse_boost_factors(query_string)
        
        # 解析分页参数
        pagination = self._parse_pagination(query_string)
        
        return ParsedQuery(
            original_query=original_query,
            query_type=query_type,
            keywords=keywords,
            semantic_terms=semantic_terms,
            filters=filters,
            facets=facets,
            boost_factors=boost_factors,
            pagination=pagination
        )
    
    def _identify_query_type(self, query_string: str) -> QueryType:
        """识别查询类型"""
        # 检查是否包含过滤条件
        has_filters = any(op in query_string for op_list in self.operators.values() for op in op_list)
        
        # 检查是否包含分面查询
        has_facets = 'group by' in query_string.lower() or '分组' in query_string
        
        # 检查查询复杂度
        word_count = len(query_string.split())
        char_count = len(query_string)
        
        # 简单规则判断
        if has_filters and has_facets:
            return QueryType.FACET
        elif has_filters:
            return QueryType.FILTER
        elif word_count > 10 or char_count > 50:
            # 长查询倾向于语义搜索
            return QueryType.SEMANTIC
        else:
            # 短查询使用关键词搜索
            return QueryType.KEYWORD
    
    def _extract_keywords(self, query_string: str) -> List[str]:
        """提取关键词"""
        # 移除操作符和特殊字符
        clean_query = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', query_string)
        
        # 中文分词
        chinese_words = list(jieba.cut(clean_query))
        
        # 英文分词
        english_words = re.findall(r'[a-zA-Z]+', query_string)
        
        # 合并并去重
        all_words = chinese_words + english_words
        keywords = list(set(word.strip() for word in all_words if len(word.strip()) > 1))
        
        # 移除停用词
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = [word for word in keywords if word not in stop_words]
        
        return keywords
    
    def _extract_semantic_terms(self, query_string: str) -> List[str]:
        """提取语义术语（用于向量搜索）"""
        # 使用TF-IDF提取重要词汇
        try:
            # 提取前5个最重要的关键词
            important_terms = jieba.analyse.extract_tags(query_string, topK=5, withWeight=False)
            return list(important_terms)
        except Exception:
            # 如果TF-IDF失败，回退到普通关键词提取
            return self._extract_keywords(query_string)[:3]
    
    def _parse_filters(self, query_string: str) -> Dict[str, Any]:
        """解析过滤条件"""
        filters = {}
        
        # 解析字段过滤 (field:value 格式)
        field_patterns = [
            r'(\w+)[\s:：=]+([^:：=\s]+)',  # 英文字段
            r'([\u4e00-\u9fff]+)[\s:：=]+([^:：=\s]+)'  # 中文字段
        ]
        
        for pattern in field_patterns:
            matches = re.findall(pattern, query_string)
            for field, value in matches:
                # 映射中文字段名
                if field in self.field_mappings:
                    field = self.field_mappings[field]
                filters[field] = value
        
        # 解析范围查询
        range_patterns = [
            r'(\w+)\s*(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)',  # 数值范围
            r'(\w+)\s*"([^"]+)"\s*[-~至到]\s*"([^"]+)"'  # 字符串范围
        ]
        
        for pattern in range_patterns:
            matches = re.findall(pattern, query_string)
            for field, start, end in matches:
                if field in self.field_mappings:
                    field = self.field_mappings[field]
                filters[f"{field}_range"] = {"gte": start, "lte": end}
        
        return filters
    
    def _parse_facets(self, query_string: str) -> List[str]:
        """解析分面字段"""
        facets = []
        
        # 查找分组字段
        group_patterns = [
            r'group\s+by\s+(\w+)',
            r'分组\s*[:：]?\s*([\u4e00-\u9fff\w]+)',
            r'按\s*([\u4e00-\u9fff\w]+)\s*分组'
        ]
        
        for pattern in group_patterns:
            matches = re.findall(pattern, query_string, re.IGNORECASE)
            for match in matches:
                # 映射字段名
                field = match if match in self.field_mappings.values() else self.field_mappings.get(match, match)
                facets.append(field)
        
        return facets
    
    def _parse_boost_factors(self, query_string: str) -> Dict[str, float]:
        """解析权重因子"""
        boosts = {}
        
        # 查找权重标记 (^2, ^0.5 等)
        boost_patterns = [
            r'(\w+)\^(\d+(?:\.\d+)?)',  # 英文字段加权
            r'([\u4e00-\u9fff]+)\^(\d+(?:\.\d+)?)'  # 中文字段加权
        ]
        
        for pattern in boost_patterns:
            matches = re.findall(pattern, query_string)
            for field, weight in matches:
                weight_value = float(weight)
                if field in self.field_mappings:
                    field = self.field_mappings[field]
                boosts[field] = weight_value
        
        return boosts
    
    def _parse_pagination(self, query_string: str) -> Dict[str, int]:
        """解析分页参数"""
        pagination = {"page": 1, "size": 10}
        
        # 查找分页参数
        page_patterns = [
            r'page\s*[=:]\s*(\d+)',
            r'size\s*[=:]\s*(\d+)',
            r'第\s*(\d+)\s*页',
            r'每页\s*(\d+)\s*条'
        ]
        
        for pattern in page_patterns:
            matches = re.findall(pattern, query_string, re.IGNORECASE)
            for match in matches:
                if 'page' in pattern.lower() or '第' in pattern:
                    pagination["page"] = int(match)
                elif 'size' in pattern.lower() or '每页' in pattern:
                    pagination["size"] = int(match)
        
        return pagination

class QueryRewriter:
    """查询重写器"""
    
    def __init__(self):
        # 同义词词典
        self.synonyms = {
            '人工智能': ['AI', '机器智能', '人工智慧'],
            '机器学习': ['ML', '机器学习算法'],
            '深度学习': ['DL', '深度神经网络'],
            '自然语言处理': ['NLP', '文本处理'],
            '计算机视觉': ['CV', '图像识别'],
            '数据科学': ['数据分析', '大数据分析'],
            '云计算': ['云服务', '云端计算'],
            '区块链': ['分布式账本', '加密货币']
        }
    
    def rewrite(self, parsed_query: ParsedQuery) -> ParsedQuery:
        """
        重写查询以提高召回率
        
        Args:
            parsed_query: 解析后的查询对象
            
        Returns:
            重写后的查询对象
        """
        # 扩展同义词
        expanded_keywords = self._expand_synonyms(parsed_query.keywords)
        parsed_query.keywords.extend(expanded_keywords)
        
        # 生成变体查询
        variants = self._generate_variants(parsed_query.original_query)
        parsed_query.semantic_terms.extend(variants)
        
        # 优化过滤条件
        optimized_filters = self._optimize_filters(parsed_query.filters)
        parsed_query.filters.update(optimized_filters)
        
        return parsed_query
    
    def _expand_synonyms(self, keywords: List[str]) -> List[str]:
        """扩展同义词"""
        expanded = []
        for keyword in keywords:
            if keyword in self.synonyms:
                expanded.extend(self.synonyms[keyword])
        return list(set(expanded))  # 去重
    
    def _generate_variants(self, query_string: str) -> List[str]:
        """生成查询变体"""
        variants = []
        
        # 生成截断变体
        words = query_string.split()
        if len(words) > 2:
            # 取前几个词
            variants.append(' '.join(words[:2]))
            # 取后几个词
            variants.append(' '.join(words[-2:]))
        
        # 生成单个重要词
        important_words = jieba.analyse.extract_tags(query_string, topK=3)
        variants.extend(important_words)
        
        return list(set(variants))
    
    def _optimize_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """优化过滤条件"""
        optimized = {}
        
        # 标准化日期格式
        if 'created_at' in filters:
            date_value = filters['created_at']
            # 这里可以添加日期格式标准化逻辑
            optimized['created_at_normalized'] = date_value
        
        # 优化数值范围
        for key, value in filters.items():
            if '_range' in key and isinstance(value, dict):
                # 确保范围值是正确的类型
                if 'gte' in value:
                    try:
                        value['gte'] = float(value['gte'])
                    except ValueError:
                        pass
                if 'lte' in value:
                    try:
                        value['lte'] = float(value['lte'])
                    except ValueError:
                        pass
        
        return optimized

class QueryValidator:
    """查询验证器"""
    
    def __init__(self):
        self.max_query_length = 1000
        self.max_keywords = 50
        self.allowed_fields = {'title', 'author', 'content_type', 'language', 'category', 'created_at'}
    
    def validate(self, parsed_query: ParsedQuery) -> Tuple[bool, List[str]]:
        """
        验证查询的有效性
        
        Args:
            parsed_query: 解析后的查询对象
            
        Returns:
            (是否有效, 错误消息列表)
        """
        errors = []
        
        # 验证查询长度
        if len(parsed_query.original_query) > self.max_query_length:
            errors.append(f"查询长度超过限制 ({self.max_query_length} 字符)")
        
        # 验证关键词数量
        if len(parsed_query.keywords) > self.max_keywords:
            errors.append(f"关键词数量超过限制 ({self.max_keywords} 个)")
        
        # 验证字段名
        for field in parsed_query.filters.keys():
            base_field = field.replace('_range', '').replace('_normalized', '')
            if base_field not in self.allowed_fields:
                errors.append(f"不支持的字段: {field}")
        
        # 验证分页参数
        if parsed_query.pagination["page"] < 1:
            errors.append("页码必须大于0")
        if parsed_query.pagination["size"] < 1 or parsed_query.pagination["size"] > 100:
            errors.append("页面大小必须在1-100之间")
        
        # 验证权重因子
        for field, weight in parsed_query.boost_factors.items():
            if weight <= 0 or weight > 10:
                errors.append(f"权重因子 {field} 必须在0-10之间")
        
        return len(errors) == 0, errors

# 主查询处理器类
class QueryProcessor:
    """主查询处理器"""
    
    def __init__(self):
        self.parser = QueryParser()
        self.rewriter = QueryRewriter()
        self.validator = QueryValidator()
    
    def process_query(self, query_string: str) -> Tuple[ParsedQuery, List[str]]:
        """
        处理查询
        
        Args:
            query_string: 原始查询字符串
            
        Returns:
            (解析后的查询对象, 错误消息列表)
        """
        try:
            # 1. 解析查询
            parsed_query = self.parser.parse(query_string)
            
            # 2. 重写查询
            rewritten_query = self.rewriter.rewrite(parsed_query)
            
            # 3. 验证查询
            is_valid, errors = self.validator.validate(rewritten_query)
            
            if not is_valid:
                return rewritten_query, errors
            
            return rewritten_query, []
            
        except Exception as e:
            return None, [f"查询处理失败: {str(e)}"]
    
    def get_query_analysis(self, query_string: str) -> Dict[str, Any]:
        """获取查询分析信息"""
        parsed_query, errors = self.process_query(query_string)
        
        if parsed_query is None:
            return {"error": errors[0] if errors else "未知错误"}
        
        return {
            "original_query": parsed_query.original_query,
            "query_type": parsed_query.query_type.value,
            "keywords": parsed_query.keywords,
            "semantic_terms": parsed_query.semantic_terms,
            "filters": parsed_query.filters,
            "facets": parsed_query.facets,
            "boost_factors": parsed_query.boost_factors,
            "pagination": parsed_query.pagination,
            "errors": errors,
            "analysis": {
                "keyword_count": len(parsed_query.keywords),
                "has_filters": len(parsed_query.filters) > 0,
                "has_facets": len(parsed_query.facets) > 0,
                "complexity_score": self._calculate_complexity(parsed_query)
            }
        }
    
    def _calculate_complexity(self, parsed_query: ParsedQuery) -> float:
        """计算查询复杂度分数 (0-1)"""
        score = 0.0
        
        # 基础分数
        score += 0.2
        
        # 关键词数量影响
        keyword_factor = min(1.0, len(parsed_query.keywords) / 10)
        score += keyword_factor * 0.3
        
        # 过滤条件影响
        filter_factor = min(1.0, len(parsed_query.filters) / 5)
        score += filter_factor * 0.3
        
        # 分面查询影响
        if parsed_query.facets:
            score += 0.2
        
        return min(1.0, score)

# 导出主要类
__all__ = ['QueryType', 'ParsedQuery', 'QueryProcessor', 'QueryParser', 'QueryRewriter', 'QueryValidator']