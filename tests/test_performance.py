#!/usr/bin/env python3
"""性能优化和测试脚本"""

import sys
import os
import time
import asyncio
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor
import psutil

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

class PerformanceTester:
    """性能测试器"""
    
    def __init__(self):
        """初始化性能测试器"""
        self.results = {}
        self.system_info = self._get_system_info()
    
    def _get_system_info(self):
        """获取系统信息"""
        return {
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total / (1024**3),  # GB
            "platform": sys.platform,
            "python_version": sys.version
        }
    
    def measure_time(self, func, *args, **kwargs):
        """测量函数执行时间"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    def test_document_processing_performance(self):
        """测试文档处理性能"""
        logger.info("=== 测试文档处理性能 ===")
        
        try:
            from services.document_processor import DocumentProcessor, ProcessingConfig
            from services.chunking_engine import ChunkingEngine
            
            processor = DocumentProcessor()
            chunking_engine = ChunkingEngine()
            
            # 创建不同大小的测试文档
            test_sizes = [100, 500, 1000, 2000]  # 字符数
            results = {}
            
            for size in test_sizes:
                # 生成测试内容
                test_content = "这是测试文档内容。" * (size // 10)
                test_file = Path(f"perf_test_doc_{size}.txt")
                test_file.write_text(test_content, encoding='utf-8')
                
                try:
                    # 测试文档处理时间
                    config = ProcessingConfig(chunk_size=300, chunk_overlap=50)
                    result, process_time = self.measure_time(
                        processor.process_document, str(test_file), config
                    )
                    
                    # 测试分块时间
                    chunks, chunk_time = self.measure_time(
                        chunking_engine.smart_chunk_text, test_content, config
                    )
                    
                    results[size] = {
                        "process_time": process_time,
                        "chunk_time": chunk_time,
                        "chunks_count": len(chunks),
                        "characters_per_second": size / process_time if process_time > 0 else 0
                    }
                    
                    logger.info(f"文档大小 {size} 字符: 处理时间 {process_time:.3f}s, "
                              f"分块时间 {chunk_time:.3f}s, "
                              f"处理速度 {results[size]['characters_per_second']:.0f} 字符/秒")
                    
                finally:
                    if test_file.exists():
                        test_file.unlink()
            
            self.results['document_processing'] = results
            return True
            
        except Exception as e:
            logger.error(f"文档处理性能测试失败: {e}")
            return False
    
    def test_embedding_performance(self):
        """测试向量编码性能"""
        logger.info("=== 测试向量编码性能 ===")
        
        try:
            from services.embedding_encoder import EmbeddingEncoder
            
            encoder = EmbeddingEncoder()
            
            # 测试不同批次大小
            batch_sizes = [1, 5, 10, 20]
            test_text = "这是用于测试向量编码性能的示例文本。"
            results = {}
            
            for batch_size in batch_sizes:
                texts = [test_text] * batch_size
                
                # 测试单个编码
                if batch_size == 1:
                    result, encode_time = self.measure_time(encoder.encode, test_text)
                    results[batch_size] = {
                        "encode_time": encode_time,
                        "dimensions": len(result) if result is not None else 0,
                        "texts_per_second": 1 / encode_time if encode_time > 0 else 0
                    }
                else:
                    # 测试批量编码
                    result, encode_time = self.measure_time(encoder.encode_batch, texts)
                    results[batch_size] = {
                        "encode_time": encode_time,
                        "dimensions": len(result[0]) if result and len(result) > 0 else 0,
                        "texts_per_second": batch_size / encode_time if encode_time > 0 else 0
                    }
                
                logger.info(f"批次大小 {batch_size}: 编码时间 {encode_time:.3f}s, "
                          f"处理速度 {results[batch_size]['texts_per_second']:.1f} 文本/秒")
            
            self.results['embedding'] = results
            return True
            
        except Exception as e:
            logger.error(f"向量编码性能测试失败: {e}")
            return False
    
    def test_search_performance(self):
        """测试搜索性能"""
        logger.info("=== 测试搜索性能 ===")
        
        try:
            from services.search_service import SearchService
            from services.query_processor import QueryProcessor
            
            search_service = SearchService()
            query_processor = QueryProcessor()
            
            # 测试查询处理性能
            test_queries = [
                "人工智能技术",
                "机器学习算法研究",
                "深度学习在图像识别中的应用",
                "自然语言处理最新进展"
            ]
            
            query_times = []
            for query in test_queries:
                result, process_time = self.measure_time(
                    query_processor.process_query, query
                )
                query_times.append(process_time)
            
            avg_query_time = sum(query_times) / len(query_times)
            logger.info(f"查询处理平均时间: {avg_query_time:.4f}s")
            
            self.results['search'] = {
                "avg_query_processing_time": avg_query_time,
                "query_count": len(test_queries)
            }
            return True
            
        except Exception as e:
            logger.error(f"搜索性能测试失败: {e}")
            return False
    
    def test_concurrent_performance(self):
        """测试并发性能"""
        logger.info("=== 测试并发性能 ===")
        
        try:
            from services.document_processor import DocumentProcessor, ProcessingConfig
            
            processor = DocumentProcessor()
            config = ProcessingConfig(chunk_size=200, chunk_overlap=30)
            
            # 创建多个测试文档
            test_docs = []
            for i in range(5):
                content = f"这是并发测试文档 {i} 的内容。" * 20
                test_file = Path(f"concurrent_test_{i}.txt")
                test_file.write_text(content, encoding='utf-8')
                test_docs.append((str(test_file), config))
            
            def process_single_doc(args):
                file_path, config = args
                return processor.process_document(file_path, config)
            
            # 测试串行处理
            start_time = time.time()
            serial_results = []
            for doc_args in test_docs:
                result = process_single_doc(doc_args)
                serial_results.append(result)
            serial_time = time.time() - start_time
            
            # 测试并发处理
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=3) as executor:
                concurrent_results = list(executor.map(process_single_doc, test_docs))
            concurrent_time = time.time() - start_time
            
            # 清理测试文件
            for file_path, _ in test_docs:
                if Path(file_path).exists():
                    Path(file_path).unlink()
            
            speedup = serial_time / concurrent_time if concurrent_time > 0 else 0
            efficiency = speedup / 3 * 100  # 3个线程
            
            logger.info(f"串行处理时间: {serial_time:.3f}s")
            logger.info(f"并发处理时间: {concurrent_time:.3f}s")
            logger.info(f"加速比: {speedup:.2f}x")
            logger.info(f"效率: {efficiency:.1f}%")
            
            self.results['concurrent'] = {
                "serial_time": serial_time,
                "concurrent_time": concurrent_time,
                "speedup": speedup,
                "efficiency": efficiency
            }
            return True
            
        except Exception as e:
            logger.error(f"并发性能测试失败: {e}")
            return False
    
    def generate_report(self):
        """生成性能报告"""
        logger.info("\n" + "="*60)
        logger.info("性能测试报告")
        logger.info("="*60)
        
        # 系统信息
        logger.info(f"系统信息:")
        logger.info(f"  CPU核心数: {self.system_info['cpu_count']}")
        logger.info(f"  总内存: {self.system_info['memory_total']:.1f} GB")
        logger.info(f"  平台: {self.system_info['platform']}")
        logger.info(f"  Python版本: {self.system_info['python_version'][:50]}...")
        
        # 文档处理性能
        if 'document_processing' in self.results:
            logger.info(f"\n文档处理性能:")
            for size, metrics in self.results['document_processing'].items():
                logger.info(f"  {size}字符: {metrics['characters_per_second']:.0f} 字符/秒")
        
        # 向量编码性能
        if 'embedding' in self.results:
            logger.info(f"\n向量编码性能:")
            for batch_size, metrics in self.results['embedding'].items():
                logger.info(f"  批次{batch_size}: {metrics['texts_per_second']:.1f} 文本/秒")
        
        # 搜索性能
        if 'search' in self.results:
            logger.info(f"\n搜索性能:")
            search_metrics = self.results['search']
            logger.info(f"  平均查询处理时间: {search_metrics['avg_query_processing_time']*1000:.2f} ms")
        
        # 并发性能
        if 'concurrent' in self.results:
            logger.info(f"\n并发性能:")
            concurrent_metrics = self.results['concurrent']
            logger.info(f"  加速比: {concurrent_metrics['speedup']:.2f}x")
            logger.info(f"  效率: {concurrent_metrics['efficiency']:.1f}%")
        
        logger.info("="*60)

async def main():
    """主函数"""
    logger.info("开始性能优化测试")
    
    tester = PerformanceTester()
    
    # 执行各项性能测试
    tests = [
        ("文档处理性能", tester.test_document_processing_performance),
        ("向量编码性能", tester.test_embedding_performance),
        ("搜索性能", tester.test_search_performance),
        ("并发性能", tester.test_concurrent_performance)
    ]
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if success:
                logger.info(f"✓ {test_name} 测试完成")
            else:
                logger.error(f"✗ {test_name} 测试失败")
        except Exception as e:
            logger.error(f"✗ {test_name} 测试异常: {e}")
    
    # 生成报告
    tester.generate_report()
    
    logger.info("性能测试完成！")

if __name__ == "__main__":
    asyncio.run(main())