"""检查文档表"""
import sys
sys.path.insert(0, '.')

from services.database import db

docs = db.fetchall('SELECT id, filename, status, created_at FROM documents ORDER BY created_at DESC LIMIT 10')
print('最近10条文档:')
for d in docs:
    print(f"  {d['id']} | {d['filename']} | {d['status']} | {d['created_at']}")
