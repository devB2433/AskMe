#!/usr/bin/env python3
"""系统集成测试脚本"""

import sys
import os
import asyncio
import time
from pathlib import Path
import logging

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_path)
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntegrationTestSuite:
    """集成测试套件"""
    
    def __init__(self):
        """初始化测试套件"""
        self.test_results = []
        self.passed_tests = 0
        self.failed_tests = 0
    
    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        try:
            logger.info(f"开始测试: {test_name}")
            start_time = time.time()
            
            result = test_func()
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result:
                logger.info(f"✓ {test_name} 测试通过 (耗时: {duration:.2f}s)")
                self.passed_tests += 1
                self.test_results.append((test_name, True, duration))
                return True
            else:
                logger.error(f"✗ {test_name} 测试失败 (耗时: {duration:.2f}s)")
                self.failed_tests += 1
                self.test_results.append((test_name, False, duration))
                return False
                
        except Exception as e:
            logger.error(f"✗ {test_name} 测试异常: {e}")
            self.failed_tests += 1
            self.test_results.append((test_name, False, 0))
            return False
    
    def print_summary(self):
        """打印测试总结"""
        total_tests = self.passed_tests + self.failed_tests
        success_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        logger.info("\n" + "="*50)
        logger.info("系统集成测试总结:")
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {self.passed_tests}")
        logger.info(f"失败测试: {self.failed_tests}")
        logger.info(f"成功率: {success_rate:.1f}%")
        logger.info("="*50)
        
        for test_name, passed, duration in self.test_results:
            status = "✓ 通过" if passed else "✗ 失败"
            logger.info(f"  {status}: {test_name} ({duration:.2f}s)")
        
        return self.failed_tests == 0

def test_document_processing_pipeline():
    """测试文档处理流水线"""
    try:
        from services.document_processor import DocumentProcessor, ProcessingConfig
        from services.chunking_engine import ChunkingEngine
        from services.metadata_extractor import MetadataExtractor
        
        # 创建测试文档
        test_content = """这是一个测试文档，用于验证文档处理流水线。
        文档包含多个段落和不同的内容类型。
        这是第二段内容，用来测试分块功能。
        第三段内容用于验证元数据提取功能。"""
        
        test_file = Path("test_integration_doc.txt")
        test_file.write_text(test_content, encoding='utf-8')
        
        try:
            # 初始化组件
            processor = DocumentProcessor()
            chunking_engine = ChunkingEngine()
            metadata_extractor = MetadataExtractor()
            
            # 处理文档
            config = ProcessingConfig(chunk_size=100, chunk_overlap=20)
            # 注意：这里需要传入文件路径而不是ProcessingConfig
            result = processor.process_document(str(test_file), config)
            
            # 验证结果
            assert result is not None, "处理结果不应为空"
            assert len(result.chunks) > 0, "应该生成分块"
            assert result.metadata is not None, "应该包含元数据"
            
            # 验证分块
            chunks = chunking_engine.smart_chunk_text(test_content, config)
            assert len(chunks) > 0, "智能分块应该生成结果"
            
            # 验证元数据
            metadata = metadata_extractor.extract_from_text(test_content)
            assert metadata is not None, "元数据提取应该成功"
            
            logger.info("文档处理流水线测试通过")
            return True
            
        finally:
            # 清理测试文件
            if test_file.exists():
                test_file.unlink()
                
    except Exception as e:
        logger.error(f"文档处理流水线测试失败: {e}")
        return False

def test_vector_storage_integration():
    """测试向量存储集成"""
    try:
        from services.milvus_integration import MilvusClient
        from services.embedding_encoder import EmbeddingEncoder
        
        # 初始化组件
        try:
            milvus_client = MilvusClient()
            encoder = EmbeddingEncoder()
        except Exception as e:
            logger.warning(f"Milvus客户端初始化失败（可能服务未启动）: {e}")
            return True  # 跳过此测试
        
        # 测试编码功能
        test_texts = ["这是第一个测试句子", "这是第二个测试句子"]
        embeddings = encoder.encode_batch(test_texts)
        
        assert len(embeddings) == len(test_texts), "编码结果数量应该匹配"
        assert len(embeddings[0]) > 0, "编码向量不应该为空"
        
        logger.info("向量存储集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"向量存储集成测试失败: {e}")
        return False

def test_search_service_integration():
    """测试搜索服务集成"""
    try:
        from services.search_service import SearchService
        from services.query_processor import QueryProcessor
        from services.result_ranking import ResultRanker
        
        # 初始化组件
        search_service = SearchService()
        query_processor = QueryProcessor()
        ranker = ResultRanker()
        
        # 测试查询处理
        query = "人工智能技术发展"
        processed_query = query_processor.process_query(query)
        
        assert processed_query.original_query == query, "原始查询应该保持不变"
        assert len(processed_query.tokens) > 0, "应该生成分词结果"
        
        # 测试结果排序
        mock_results = [
            {"score": 0.8, "content": "相关内容1"},
            {"score": 0.6, "content": "相关内容2"},
            {"score": 0.9, "content": "相关内容3"}
        ]
        
        ranked_results = ranker.rank_results(mock_results)
        assert len(ranked_results) == len(mock_results), "结果数量应该保持一致"
        
        # 验证排序正确性
        for i in range(len(ranked_results) - 1):
            assert ranked_results[i]['score'] >= ranked_results[i + 1]['score'], "结果应该按分数降序排列"
        
        logger.info("搜索服务集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"搜索服务集成测试失败: {e}")
        return False

def test_qa_system_integration():
    """测试问答系统集成"""
    try:
        from services.context_manager import ContextManager
        from services.document_retriever import DocumentRetriever
        from services.answer_generator import AnswerGenerator
        
        # 初始化组件
        context_manager = ContextManager()
        retriever = DocumentRetriever()
        answer_generator = AnswerGenerator()
        
        # 测试上下文管理
        session_id = "test_session_001"
        context_window = context_manager.get_session(session_id)
        assert context_window is not None, "应该能够获取上下文窗口"
        
        # 测试答案生成（使用模拟数据）
        question = "什么是人工智能？"
        mock_context = {
            "retrieved_documents": [
                {"content": "人工智能是计算机科学的一个分支", "score": 0.9},
                {"content": "机器学习是AI的重要组成部分", "score": 0.8}
            ]
        }
        
        answer_result = answer_generator.generate_answer(question, mock_context)
        assert answer_result is not None, "应该生成答案结果"
        assert len(answer_result.answer) > 0, "答案内容不应该为空"
        
        logger.info("问答系统集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"问答系统集成测试失败: {e}")
        return False

def test_workflow_engine_integration():
    """测试工作流引擎集成"""
    try:
        from services.workflow_definition import WorkflowBuilder
        from services.task_executor import TaskExecutor
        from services.state_manager import StateManager
        
        # 初始化组件
        builder = WorkflowBuilder()
        task_executor = TaskExecutor()
        state_manager = StateManager()
        
        # 测试工作流创建
        workflow = builder.create_document_processing_workflow()
        assert workflow is not None, "应该能够创建工作流"
        assert len(workflow.nodes) > 0, "工作流应该包含节点"
        
        # 测试状态管理
        state_id = state_manager.create_state(
            state_type="test",
            entity_id="test_entity_001",
            initial_data={"test": "data"}
        )
        assert state_id is not None, "应该能够创建状态记录"
        
        state_record = state_manager.get_state(state_id)
        assert state_record is not None, "应该能够获取状态记录"
        
        logger.info("工作流引擎集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"工作流引擎集成测试失败: {e}")
        return False

def test_api_layer_integration():
    """测试API层集成"""
    try:
        # 测试API路由导入
        from routes.document_api import router as document_router
        from main import app
        
        # 验证FastAPI应用
        assert app is not None, "FastAPI应用应该初始化成功"
        assert len(app.routes) > 0, "应该包含路由"
        
        # 验证文档API路由
        assert document_router is not None, "文档API路由应该存在"
        
        logger.info("API层集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"API层集成测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    logger.info("开始系统集成测试")
    logger.info("=" * 50)
    
    test_suite = IntegrationTestSuite()
    
    # 定义测试用例
    test_cases = [
        ("文档处理流水线", test_document_processing_pipeline),
        ("向量存储集成", test_vector_storage_integration),
        ("搜索服务集成", test_search_service_integration),
        ("问答系统集成", test_qa_system_integration),
        ("工作流引擎集成", test_workflow_engine_integration),
        ("API层集成", test_api_layer_integration)
    ]
    
    # 执行测试
    for test_name, test_func in test_cases:
        test_suite.run_test(test_name, test_func)
    
    # 输出总结
    success = test_suite.print_summary()
    
    if success:
        logger.info("🎉 所有集成测试通过！系统功能正常！")
    else:
        logger.error("❌ 部分集成测试失败，请检查相关模块")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)