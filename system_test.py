"""系统集成测试脚本"""
import requests
import time
import json

class SystemIntegrationTest:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:5173"
        
    def test_backend_health(self):
        """测试后端健康检查"""
        print("1. 测试后端健康检查...")
        try:
            response = requests.get(f"{self.backend_url}/health")
            if response.status_code == 200:
                print("✓ 后端服务健康检查通过")
                return True
            else:
                print(f"✗ 后端健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ 后端健康检查异常: {e}")
            return False
    
    def test_frontend_access(self):
        """测试前端访问"""
        print("2. 测试前端访问...")
        try:
            response = requests.get(self.frontend_url)
            if response.status_code == 200:
                print("✓ 前端页面访问正常")
                return True
            else:
                print(f"✗ 前端访问失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ 前端访问异常: {e}")
            return False
    
    def test_docker_services(self):
        """测试Docker服务连接"""
        print("3. 测试Docker服务连接...")
        services = {
            "Redis": ("localhost", 6379),
            "PostgreSQL": ("localhost", 5432),
            "Milvus": ("localhost", 19530),
            "Elasticsearch": ("localhost", 9200)
        }
        
        results = {}
        for service_name, (host, port) in services.items():
            try:
                # 这里只做简单的端口检查
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    print(f"✓ {service_name} 服务连接正常 ({host}:{port})")
                    results[service_name] = True
                else:
                    print(f"✗ {service_name} 服务连接失败 ({host}:{port})")
                    results[service_name] = False
            except Exception as e:
                print(f"✗ {service_name} 连接测试异常: {e}")
                results[service_name] = False
        
        return all(results.values())
    
    def test_api_endpoints(self):
        """测试API端点"""
        print("4. 测试API端点...")
        endpoints = [
            ("/", "GET"),
            ("/health", "GET"),
            ("/docs", "GET"),  # FastAPI自动生成的文档
        ]
        
        results = []
        for endpoint, method in endpoints:
            try:
                if method == "GET":
                    response = requests.get(f"{self.backend_url}{endpoint}")
                else:
                    response = requests.post(f"{self.backend_url}{endpoint}")
                
                if response.status_code < 400:  # 2xx or 3xx
                    print(f"✓ API端点 {endpoint} 访问正常")
                    results.append(True)
                else:
                    print(f"✗ API端点 {endpoint} 访问失败: {response.status_code}")
                    results.append(False)
            except Exception as e:
                print(f"✗ API端点 {endpoint} 测试异常: {e}")
                results.append(False)
        
        return all(results)
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 50)
        print("开始系统集成测试")
        print("=" * 50)
        
        tests = [
            self.test_backend_health,
            self.test_frontend_access,
            self.test_docker_services,
            self.test_api_endpoints
        ]
        
        results = []
        for test_func in tests:
            result = test_func()
            results.append(result)
            print()
        
        print("=" * 50)
        print("测试结果汇总:")
        print("=" * 50)
        
        test_names = [
            "后端健康检查",
            "前端访问测试",
            "Docker服务连接",
            "API端点测试"
        ]
        
        for i, (test_name, result) in enumerate(zip(test_names, results)):
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{i+1}. {test_name}: {status}")
        
        overall_result = all(results)
        print(f"\n总体测试结果: {'✓ 通过' if overall_result else '✗ 失败'}")
        
        if overall_result:
            print("\n🎉 系统集成测试通过！所有基础功能正常运行。")
            print("\n系统状态:")
            print("- 后端API: http://localhost:8000")
            print("- 前端界面: http://localhost:5173")
            print("- API文档: http://localhost:8000/docs")
            print("- Milvus管理: http://localhost:9091")
        else:
            print("\n❌ 系统集成测试失败，请检查上述错误。")
        
        return overall_result

if __name__ == "__main__":
    tester = SystemIntegrationTest()
    tester.run_all_tests()