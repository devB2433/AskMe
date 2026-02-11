#!/usr/bin/env python3
"""工作流引擎综合测试"""

import sys
import os
import asyncio
import logging
from datetime import datetime

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

def test_workflow_definition():
    """测试工作流定义系统"""
    logger.info("=== 测试工作流定义系统 ===")
    
    try:
        from services.workflow_definition import (
            WorkflowBuilder, WorkflowParser, NodeType, TaskType
        )
        
        # 创建工作流构建器
        builder = WorkflowBuilder()
        
        # 测试文档处理工作流
        doc_workflow = builder.create_document_processing_workflow()
        logger.info(f"✓ 创建文档处理工作流: {doc_workflow.name}")
        logger.info(f"  - 节点数量: {len(doc_workflow.nodes)}")
        logger.info(f"  - 边数量: {len(doc_workflow.edges)}")
        
        # 测试问答增强工作流
        qa_workflow = builder.create_qa_enhancement_workflow()
        logger.info(f"✓ 创建问答增强工作流: {qa_workflow.name}")
        logger.info(f"  - 节点数量: {len(qa_workflow.nodes)}")
        logger.info(f"  - 边数量: {len(qa_workflow.edges)}")
        
        # 测试工作流解析
        parser = WorkflowParser()
        workflow_dict = parser.to_dict(doc_workflow)
        parsed_workflow = parser.parse_from_dict(workflow_dict)
        logger.info("✓ 工作流序列化/反序列化测试通过")
        
        # 验证工作流
        validation_errors = parser.validate_workflow(parsed_workflow)
        if validation_errors:
            logger.error(f"工作流验证失败: {validation_errors}")
            return False
        else:
            logger.info("✓ 工作流验证通过")
        
        return True
        
    except Exception as e:
        logger.error(f"工作流定义系统测试失败: {e}")
        return False

def test_task_executor():
    """测试任务执行器"""
    logger.info("=== 测试任务执行器 ===")
    
    try:
        from services.task_executor import TaskExecutor, WorkflowExecutor, ExecutionMode
        from services.workflow_definition import WorkflowBuilder
        
        # 创建任务执行器
        task_executor = TaskExecutor(max_workers=5, execution_mode=ExecutionMode.THREAD_POOL)
        workflow_executor = WorkflowExecutor(task_executor)
        
        logger.info("✓ 任务执行器初始化成功")
        
        # 创建测试工作流
        builder = WorkflowBuilder()
        test_workflow = builder.create_document_processing_workflow()
        
        # 执行工作流
        async def run_test():
            try:
                input_data = {
                    "documents": ["test_doc1.pdf", "test_doc2.docx"],
                    "processing_options": {"chunk_size": 500}
                }
                
                result = await workflow_executor.run_workflow(test_workflow, input_data)
                logger.info("✓ 工作流执行成功")
                logger.info(f"  - 执行ID: {result['execution_id']}")
                logger.info(f"  - 状态: {result['status']}")
                logger.info(f"  - 历史记录数: {len(result['history'])}")
                
                return True
            except Exception as e:
                logger.error(f"工作流执行失败: {e}")
                return False
        
        # 运行异步测试
        success = asyncio.run(run_test())
        return success
        
    except Exception as e:
        logger.error(f"任务执行器测试失败: {e}")
        return False

def test_state_manager():
    """测试状态管理器"""
    logger.info("=== 测试状态管理器 ===")
    
    try:
        from services.state_manager import StateManager, StateType, StateStatus
        
        # 创建状态管理器
        state_manager = StateManager()
        logger.info("✓ 状态管理器初始化成功")
        
        # 创建状态记录
        state_id = state_manager.create_state(
            state_type=StateType.WORKFLOW,
            entity_id="test_workflow_001",
            initial_data={"workflow_name": "测试工作流"},
            tags=["test", "workflow"]
        )
        logger.info(f"✓ 创建状态记录: {state_id}")
        
        # 查询状态
        states = state_manager.query_states(
            state_type=StateType.WORKFLOW,
            tags=["test"]
        )
        logger.info(f"✓ 查询到 {len(states)} 个状态记录")
        
        # 更新状态
        success = state_manager.update_state(
            state_id,
            new_status=StateStatus.ACTIVE,
            new_data={"progress": 50}
        )
        logger.info(f"✓ 状态更新 {'成功' if success else '失败'}")
        
        # 获取更新后的状态
        updated_state = state_manager.get_state(state_id)
        if updated_state:
            logger.info(f"✓ 状态数据: {updated_state.data}")
        
        return True
        
    except Exception as e:
        logger.error(f"状态管理器测试失败: {e}")
        return False

def test_scheduler():
    """测试调度器"""
    logger.info("=== 测试调度器 ===")
    
    try:
        from services.scheduler import TaskScheduler, TaskPriority, ScheduleType
        from services.state_manager import StateManager
        
        # 创建调度器
        state_manager = StateManager()
        scheduler = TaskScheduler(state_manager=state_manager, max_workers=3)
        scheduler.start()
        
        logger.info("✓ 调度器启动成功")
        
        # 调度立即执行的任务
        task_id1 = scheduler.schedule_task(
            name="立即任务测试",
            target_function="health_check",
            schedule_type=ScheduleType.IMMEDIATE,
            priority=TaskPriority.HIGH
        )
        logger.info(f"✓ 调度立即任务: {task_id1}")
        
        # 调度延迟任务
        task_id2 = scheduler.schedule_task(
            name="延迟任务测试",
            target_function="cleanup_expired",
            schedule_type=ScheduleType.DELAYED,
            delay_seconds=2,
            priority=TaskPriority.NORMAL
        )
        logger.info(f"✓ 调度延迟任务: {task_id2}")
        
        # 获取调度器统计
        stats = scheduler.get_scheduler_stats()
        logger.info(f"✓ 调度器统计: {stats}")
        
        # 等待任务执行
        import time
        time.sleep(3)
        
        # 检查任务状态
        task_status = scheduler.get_task_status(task_id1)
        if task_status:
            logger.info(f"✓ 任务1状态: {task_status.status}")
        
        # 停止调度器
        scheduler.stop()
        logger.info("✓ 调度器停止成功")
        
        return True
        
    except Exception as e:
        logger.error(f"调度器测试失败: {e}")
        return False

def test_integration():
    """测试整体集成"""
    logger.info("=== 测试整体集成 ===")
    
    try:
        # 导入所有组件
        from services.workflow_definition import WorkflowBuilder
        from services.task_executor import TaskExecutor, WorkflowExecutor
        from services.state_manager import StateManager
        from services.scheduler import TaskScheduler, WorkflowScheduler, TaskPriority
        
        # 创建各组件实例
        state_manager = StateManager()
        task_executor = TaskExecutor()
        workflow_executor = WorkflowExecutor(task_executor)
        task_scheduler = TaskScheduler(state_manager=state_manager)
        workflow_scheduler = WorkflowScheduler(task_scheduler)
        
        logger.info("✓ 所有组件初始化成功")
        
        # 创建测试工作流
        builder = WorkflowBuilder()
        test_workflow = builder.create_qa_enhancement_workflow()
        
        # 调度工作流执行
        task_scheduler.start()
        
        workflow_task_id = workflow_scheduler.schedule_workflow(
            workflow_definition={
                "name": test_workflow.name,
                "nodes": [node.__dict__ for node in test_workflow.nodes],
                "edges": [edge.__dict__ for edge in test_workflow.edges]
            },
            trigger_params={"question": "什么是人工智能？"},
            priority=TaskPriority.HIGH
        )
        
        logger.info(f"✓ 调度工作流任务: {workflow_task_id}")
        
        # 等待执行
        import time
        time.sleep(2)
        
        # 检查执行状态
        task_status = task_scheduler.get_task_status(workflow_task_id)
        if task_status:
            logger.info(f"✓ 工作流任务状态: {task_status.status}")
        
        task_scheduler.stop()
        
        logger.info("✓ 整体集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"整体集成测试失败: {e}")
        return False

def main():
    """主测试函数"""
    logger.info("开始工作流引擎综合测试")
    logger.info("=" * 50)
    
    test_results = []
    
    # 逐个运行测试
    tests = [
        ("工作流定义系统", test_workflow_definition),
        ("任务执行器", test_task_executor),
        ("状态管理器", test_state_manager),
        ("调度器", test_scheduler),
        ("整体集成", test_integration)
    ]
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n开始测试: {test_name}")
            result = test_func()
            test_results.append((test_name, result))
            if result:
                logger.info(f"✓ {test_name} 测试通过")
            else:
                logger.error(f"✗ {test_name} 测试失败")
        except Exception as e:
            logger.error(f"✗ {test_name} 测试异常: {e}")
            test_results.append((test_name, False))
    
    # 输出测试总结
    logger.info("\n" + "=" * 50)
    logger.info("工作流引擎综合测试总结:")
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"  {status}: {test_name}")
    
    logger.info(f"\n总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！工作流引擎模块开发完成！")
        return True
    else:
        logger.error("❌ 部分测试失败，请检查相关模块")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)