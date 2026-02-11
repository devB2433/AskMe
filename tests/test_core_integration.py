#!/usr/bin/env python3
"""核心功能集成测试脚本"""

import sys
import os
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

def test_core_modules():
    """测试核心模块导入和基本功能"""
    logger.info("=== 测试核心模块功能 ===")
    
    tests_passed = 0
    tests_total = 0
    
    # 测试文档处理模块
    try:
        tests_total += 1
        from services.document_processor import DocumentProcessor, ProcessingConfig
        processor = DocumentProcessor()
        config = ProcessingConfig()
        logger.info("✓ 文档处理模块导入成功")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ 文档处理模块测试失败: {e}")
    
    # 测试向量存储模块
    try:
        tests_total += 1
        from services.milvus_integration import MilvusClient
        from services.embedding_encoder import EmbeddingEncoder
        
        # 尝试初始化（即使服务未运行也要测试导入）
        try:
            milvus_client = MilvusClient()
            logger.info("✓ Milvus客户端初始化成功")
        except Exception as e:
            logger.warning(f"⚠ Milvus连接失败（正常，服务可能未启动）: {e}")
        
        encoder = EmbeddingEncoder()
        logger.info("✓ 嵌入编码器初始化成功")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ 向量存储模块测试失败: {e}")
    
    # 测试搜索服务模块
    try:
        tests_total += 1
        from services.search_service import SearchService
        from services.query_processor import QueryProcessor
        from services.result_ranking import ResultRanker
        
        search_service = SearchService()
        query_processor = QueryProcessor()
        ranker = ResultRanker()
        logger.info("✓ 搜索服务模块初始化成功")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ 搜索服务模块测试失败: {e}")
    
    # 测试问答系统模块
    try:
        tests_total += 1
        from services.context_manager import ContextManager
        from services.answer_generator import AnswerGenerator
        from services.source_tracker import SourceTracker
        
        context_manager = ContextManager()
        answer_generator = AnswerGenerator()
        source_tracker = SourceTracker()
        logger.info("✓ 问答系统模块初始化成功")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ 问答系统模块测试失败: {e}")
    
    # 测试工作流引擎模块
    try:
        tests_total += 1
        from services.workflow_definition import WorkflowBuilder
        from services.task_executor import TaskExecutor
        from services.state_manager import StateManager
        
        builder = WorkflowBuilder()
        task_executor = TaskExecutor()
        state_manager = StateManager()
        logger.info("✓ 工作流引擎模块初始化成功")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ 工作流引擎模块测试失败: {e}")
    
    # 测试API层
    try:
        tests_total += 1
        from routes.document_api import router as document_router
        from main import app
        logger.info("✓ API层模块导入成功")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ API层模块测试失败: {e}")
    
    return tests_passed, tests_total

def test_basic_functionality():
    """测试基本功能"""
    logger.info("=== 测试基本功能 ===")
    
    tests_passed = 0
    tests_total = 0
    
    # 测试工作流构建
    try:
        tests_total += 1
        from services.workflow_definition import WorkflowBuilder
        
        builder = WorkflowBuilder()
        workflow = builder.create_document_processing_workflow()
        
        assert workflow is not None, "应该能够创建工作流"
        assert len(workflow.nodes) > 0, "工作流应该包含节点"
        logger.info(f"✓ 工作流构建功能正常，包含 {len(workflow.nodes)} 个节点")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ 工作流构建测试失败: {e}")
    
    # 测试状态管理
    try:
        tests_total += 1
        from services.state_manager import StateManager, StateType, StateStatus
        
        state_manager = StateManager()
        state_id = state_manager.create_state(
            state_type=StateType.WORKFLOW,
            entity_id="test_workflow_001",
            initial_data={"test": "data"}
        )
        
        assert state_id is not None, "应该能够创建状态"
        state_record = state_manager.get_state(state_id)
        assert state_record is not None, "应该能够获取状态"
        logger.info("✓ 状态管理功能正常")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ 状态管理测试失败: {e}")
    
    return tests_passed, tests_total

def main():
    """主测试函数"""
    logger.info("开始核心功能集成测试")
    logger.info("=" * 50)
    
    start_time = time.time()
    
    # 执行模块测试
    module_passed, module_total = test_core_modules()
    
    # 执行功能测试
    func_passed, func_total = test_basic_functionality()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 计算总结果
    total_passed = module_passed + func_passed
    total_tests = module_total + func_total
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    # 输出总结
    logger.info("\n" + "=" * 50)
    logger.info("核心功能集成测试总结:")
    logger.info(f"总测试数: {total_tests}")
    logger.info(f"通过测试: {total_passed}")
    logger.info(f"失败测试: {total_tests - total_passed}")
    logger.info(f"成功率: {success_rate:.1f}%")
    logger.info(f"总耗时: {total_time:.2f}秒")
    logger.info("=" * 50)
    
    if total_passed == total_tests:
        logger.info("🎉 所有核心功能测试通过！系统基础功能正常！")
        return True
    else:
        logger.error("❌ 部分核心功能测试失败，请检查相关模块")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)