"""数据迁移脚本：从JSON迁移到SQLite"""
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import db
from services.state_manager import StateManager, StateType, StateStatus


def migrate_users():
    """迁移用户数据"""
    user_file = Path("data/users.json")
    if not user_file.exists():
        print("用户数据文件不存在，跳过")
        return
    
    with open(user_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    users = data.get('users', [])
    if not users:
        print("没有用户数据需要迁移")
        return
    
    print(f"开始迁移 {len(users)} 个用户...")
    
    for user in users:
        try:
            # 检查用户是否已存在
            existing = db.fetchone("SELECT id FROM users WHERE id = ?", (user['user_id'],))
            if existing:
                print(f"  跳过已存在用户: {user['username']}")
                continue
            
            db.execute(
                """INSERT INTO users (id, username, password_hash, name, department, email, 
                   is_active, created_at, last_login)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user['user_id'],
                    user['username'],
                    user['password_hash'],
                    user['name'],
                    user['department'],
                    user.get('email'),
                    1 if user.get('is_active', True) else 0,
                    user.get('created_at'),
                    user.get('last_login')
                )
            )
            
            # 迁移token
            for token in user.get('tokens', []):
                db.execute(
                    "INSERT INTO user_tokens (user_id, token) VALUES (?, ?)",
                    (user['user_id'], token)
                )
            
            print(f"  已迁移用户: {user['username']}")
            
        except Exception as e:
            print(f"  迁移用户失败 {user['username']}: {e}")
    
    db.conn.commit()
    print("用户数据迁移完成")


def migrate_states():
    """迁移状态记录"""
    state_file = Path("data/state_store.json")
    if not state_file.exists():
        print("状态数据文件不存在，跳过")
        return
    
    with open(state_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    states = data.get('states', [])
    if not states:
        print("没有状态数据需要迁移")
        return
    
    print(f"开始迁移 {len(states)} 条状态记录...")
    
    state_mgr = StateManager()
    
    for state in states:
        try:
            # 检查是否已存在
            existing = db.fetchone(
                "SELECT state_id FROM states WHERE state_id = ?",
                (state['state_id'],)
            )
            if existing:
                print(f"  跳过已存在状态: {state['state_id']}")
                continue
            
            # 创建状态记录
            state_type = StateType(state['state_type'])
            status = StateStatus(state['status'])
            
            state_mgr.create_state(
                state_type=state_type,
                entity_id=state['entity_id'],
                initial_data=state.get('data', {}),
                initial_status=status
            )
            
            # 如果状态不是pending，需要更新
            if status != StateStatus.PENDING:
                state_mgr.update_state(
                    state['state_id'],
                    new_status=status,
                    new_data=state.get('data', {})
                )
            
            print(f"  已迁移状态: {state['state_id']}")
            
        except Exception as e:
            print(f"  迁移状态失败 {state['state_id']}: {e}")
    
    print("状态数据迁移完成")


def migrate_documents():
    """迁移文档记录（从状态记录中提取）"""
    state_file = Path("data/state_store.json")
    if not state_file.exists():
        return
    
    with open(state_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    states = data.get('states', [])
    doc_states = [s for s in states if s.get('state_type') == 'document']
    
    if not doc_states:
        print("没有文档数据需要迁移")
        return
    
    print(f"开始迁移 {len(doc_states)} 条文档记录...")
    
    for state in doc_states:
        try:
            doc_id = state['entity_id']
            doc_data = state.get('data', {})
            
            # 检查是否已存在
            existing = db.fetchone("SELECT id FROM documents WHERE id = ?", (doc_id,))
            if existing:
                print(f"  跳过已存在文档: {doc_id}")
                continue
            
            processing_result = doc_data.get('processing_result', {})
            
            db.execute(
                """INSERT INTO documents 
                   (id, filename, content_type, team_id, uploaded_by, status, 
                    chunks_count, vector_stored, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    doc_id,
                    doc_data.get('filename', ''),
                    doc_data.get('content_type'),
                    doc_data.get('team_id', 'default'),
                    doc_data.get('uploaded_by', 'anonymous'),
                    state['status'],
                    processing_result.get('chunks_count', 0),
                    1 if processing_result.get('vector_stored') else 0,
                    state.get('created_at'),
                    state.get('updated_at')
                )
            )
            
            print(f"  已迁移文档: {doc_data.get('filename', doc_id)}")
            
        except Exception as e:
            print(f"  迁移文档失败 {state.get('entity_id')}: {e}")
    
    db.conn.commit()
    print("文档数据迁移完成")


def main():
    """主函数"""
    print("=" * 50)
    print("AskMe 数据迁移工具")
    print("从 JSON 迁移到 SQLite")
    print("=" * 50)
    
    # 确保数据库已初始化
    print("\n1. 初始化数据库...")
    # 数据库在导入时自动初始化
    
    # 迁移用户数据
    print("\n2. 迁移用户数据...")
    migrate_users()
    
    # 迁移状态记录
    print("\n3. 迁移状态记录...")
    migrate_states()
    
    # 迁移文档记录
    print("\n4. 迁移文档记录...")
    migrate_documents()
    
    print("\n" + "=" * 50)
    print("数据迁移完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
