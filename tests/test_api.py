#!/usr/bin/env python3
"""API功能测试脚本"""

import requests
import json
import time
from pathlib import Path

# API基础URL
BASE_URL = "http://localhost:8000"

def test_api_root():
    """测试API根路径"""
    print("=== 测试API根路径 ===")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✓ API根路径访问成功")
            print(f"  响应: {response.json()}")
            return True
        else:
            print(f"✗ API根路径访问失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ API根路径访问异常: {e}")
        return False

def test_health_check():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✓ 健康检查通过")
            print(f"  状态: {response.json()}")
            return True
        else:
            print(f"✗ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 健康检查异常: {e}")
        return False

def test_api_docs():
    """测试API文档"""
    print("\n=== 测试API文档 ===")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✓ Swagger文档可访问")
        else:
            print(f"✗ Swagger文档访问失败: {response.status_code}")
            
        response = requests.get(f"{BASE_URL}/redoc")
        if response.status_code == 200:
            print("✓ ReDoc文档可访问")
        else:
            print(f"✗ ReDoc文档访问失败: {response.status_code}")
            
        return True
    except Exception as e:
        print(f"✗ API文档访问异常: {e}")
        return False

def test_document_upload():
    """测试文档上传（模拟）"""
    print("\n=== 测试文档上传功能 ===")
    try:
        # 创建测试文本文件
        test_content = "这是一个测试文档内容，用于验证文档上传功能。\n包含多行文本内容用于测试分块功能。"
        test_file = Path("test_document.txt")
        test_file.write_text(test_content, encoding='utf-8')
        
        # 准备上传数据
        files = {'file': ('test_document.txt', open(test_file, 'rb'), 'text/plain')}
        data = {
            'collection_name': 'test_collection',
            'chunk_size': '300',
            'chunk_overlap': '50',
            'enable_metadata': 'true'
        }
        
        print("正在上传测试文档...")
        response = requests.post(f"{BASE_URL}/api/documents/upload", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("✓ 文档上传成功")
            print(f"  文档ID: {result.get('document_id')}")
            print(f"  文件名: {result.get('filename')}")
            print(f"  分块数量: {result.get('chunks_count')}")
            print(f"  处理时间: {result.get('processing_time')}秒")
            print(f"  状态: {result.get('status')}")
            return result.get('document_id')
        else:
            print(f"✗ 文档上传失败: {response.status_code}")
            print(f"  错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"✗ 文档上传异常: {e}")
        return None
    finally:
        # 清理测试文件
        if test_file.exists():
            test_file.unlink()

def test_document_info(document_id):
    """测试获取文档信息"""
    if not document_id:
        print("\n=== 跳过文档信息测试（无文档ID）===")
        return False
        
    print(f"\n=== 测试获取文档信息 ===")
    try:
        response = requests.get(f"{BASE_URL}/api/documents/{document_id}")
        if response.status_code == 200:
            result = response.json()
            print("✓ 获取文档信息成功")
            print(f"  文档ID: {result.get('document_id')}")
            print(f"  状态: {result.get('status')}")
            print(f"  创建时间: {result.get('created_at')}")
            return True
        else:
            print(f"✗ 获取文档信息失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取文档信息异常: {e}")
        return False

def test_document_list():
    """测试文档列表"""
    print("\n=== 测试文档列表 ===")
    try:
        response = requests.get(f"{BASE_URL}/api/documents/")
        if response.status_code == 200:
            result = response.json()
            print("✓ 获取文档列表成功")
            print(f"  文档总数: {result.get('total', 0)}")
            print(f"  返回数量: {len(result.get('documents', []))}")
            for doc in result.get('documents', [])[:3]:  # 显示前3个
                print(f"  - {doc.get('document_id')}: {doc.get('filename')} ({doc.get('status')})")
            return True
        else:
            print(f"✗ 获取文档列表失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取文档列表异常: {e}")
        return False

def main():
    """主测试函数"""
    print("开始API功能测试")
    print("=" * 50)
    
    # 等待API服务器启动
    print("等待API服务器启动...")
    time.sleep(2)
    
    test_results = []
    
    # 执行各项测试
    tests = [
        ("API根路径", test_api_root),
        ("健康检查", test_health_check),
        ("API文档", test_api_docs),
        ("文档上传", lambda: test_document_upload()),
        ("文档列表", test_document_list)
    ]
    
    document_id = None
    
    for test_name, test_func in tests:
        try:
            if test_name == "文档上传":
                document_id = test_func()
                result = document_id is not None
            elif test_name == "文档信息" and document_id:
                result = test_func(document_id)
            else:
                result = test_func()
                
            test_results.append((test_name, result))
            
            if result:
                print(f"✓ {test_name} 测试通过")
            else:
                print(f"✗ {test_name} 测试失败")
                
        except Exception as e:
            print(f"✗ {test_name} 测试异常: {e}")
            test_results.append((test_name, False))
    
    # 如果有文档上传成功，测试文档信息
    if document_id:
        info_result = test_document_info(document_id)
        test_results.append(("文档信息", info_result))
    
    # 输出测试总结
    print("\n" + "=" * 50)
    print("API功能测试总结:")
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {test_name}")
    
    print(f"\n总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有API测试通过！")
    else:
        print("⚠️  部分API测试失败")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)