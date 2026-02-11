"""清理重复数据脚本"""
import sys
sys.path.insert(0, '.')

from services.database import db

# 清理重复的documents（保留每个filename的最新一条）
print('清理重复文档...')

# 找出重复的filename
duplicates = db.fetchall('''
    SELECT filename FROM documents GROUP BY filename HAVING COUNT(*) > 1
''')

for dup in duplicates:
    filename = dup['filename']
    # 保留最新的，删除旧的
    db.execute('''
        DELETE FROM documents 
        WHERE filename = ? 
        AND id NOT IN (
            SELECT id FROM documents WHERE filename = ? ORDER BY created_at DESC LIMIT 1
        )
    ''', (filename, filename))

# 清理重复的tasks
print('清理重复任务...')

duplicates = db.fetchall('''
    SELECT filename FROM tasks GROUP BY filename HAVING COUNT(*) > 1
''')

for dup in duplicates:
    filename = dup['filename']
    db.execute('''
        DELETE FROM tasks 
        WHERE filename = ? 
        AND id NOT IN (
            SELECT id FROM tasks WHERE filename = ? ORDER BY created_at DESC LIMIT 1
        )
    ''', (filename, filename))

db.conn.commit()

# 验证
docs = db.fetchall('SELECT id, filename, team_id FROM documents ORDER BY created_at DESC')
print(f'\n清理后文档数: {len(docs)}')
for d in docs:
    print(f'  {d["filename"]} ({d["team_id"]})')

tasks = db.fetchall('SELECT id, filename, status FROM tasks ORDER BY created_at DESC')
print(f'\n清理后任务数: {len(tasks)}')
for t in tasks:
    print(f'  {t["filename"]} ({t["status"]})')
