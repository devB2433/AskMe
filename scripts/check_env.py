"""环境检查脚本"""
import sys
import subprocess
import importlib

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"✓ Python版本: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python版本过低: {version.major}.{version.minor}.{version.micro} (需要 >= 3.10)")
        return False

def check_package(package_name, import_name=None):
    """检查包是否安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        print(f"✓ {package_name}")
        return True
    except ImportError:
        print(f"✗ {package_name} 未安装")
        return False

def check_docker():
    """检查Docker是否安装并运行"""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Docker: {result.stdout.strip()}")
            
            # 检查Docker是否运行
            result = subprocess.run(['docker', 'info'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ Docker daemon 正在运行")
                return True
            else:
                print("✗ Docker daemon 未运行")
                return False
        else:
            print("✗ Docker 未安装")
            return False
    except FileNotFoundError:
        print("✗ Docker 未安装")
        return False

def main():
    print("=== AskMe 环境检查 ===\n")
    
    # 检查Python版本
    print("1. Python环境:")
    python_ok = check_python_version()
    print()
    
    # 检查必需的Python包
    print("2. Python依赖包:")
    required_packages = [
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        ('sqlalchemy', 'sqlalchemy'),
        ('psycopg2', 'psycopg2'),
        ('redis', 'redis'),
        ('pymilvus', 'pymilvus'),
        ('elasticsearch', 'elasticsearch'),
        ('sentence-transformers', 'sentence_transformers'),
        ('unstructured', 'unstructured'),
        ('torch', 'torch'),
    ]
    
    packages_ok = True
    for package, import_name in required_packages:
        if not check_package(package, import_name):
            packages_ok = False
    print()
    
    # 检查Docker
    print("3. Docker环境:")
    docker_ok = check_docker()
    print()
    
    # 总结
    print("=== 检查结果 ===")
    if python_ok and packages_ok and docker_ok:
        print("✓ 环境检查通过！可以开始开发")
        return True
    else:
        print("✗ 环境检查失败，请安装缺失的组件")
        return False

if __name__ == "__main__":
    main()