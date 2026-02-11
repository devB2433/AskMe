"""修复文档team_id脚本"""
import sys
sys.path.insert(0, '.')

from pymilvus import MilvusClient
from services.database import db
from services.embedding_encoder import EmbeddingEncoder
from services.document_processor import DocumentProcessor
from pathlib import Path
import json

def fix_team_id(doc_id, new_team_id):
    """修复文档的team_id"""
    
    # 1. 更新SQLite
    db.execute("UPDATE documents SET team_id = ? WHERE id = ?", (new_team_id, doc_id))
    db.conn.commit()
    print(f'SQLite已更新: {doc_id} -> {new_team_id}')
    
    # 2. 找到原始文档内容文件
    content_file = Path(f'uploads/{doc_id}_content.json')
    if not content_file.exists():
        print(f'内容文件不存在: {content_file}')
        return
    
    with open(content_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    chunks = data.get('chunks', [])
    print(f'找到 {len(chunks)} 个chunks')
    
    # 3. 删除Milvus中的旧记录
    client = MilvusClient(uri='http://localhost:19530')
    old_records = client.query(
        'askme_documents', 
        filter=f'document_id == "{doc_id}"',
        output_fields=['id'],
        limit=1000
    )
    if old_records:
        ids_to_delete = [r['id'] for r in old_records]
        client.delete('askme_documents', ids=ids_to_delete)
        print(f'已删除 {len(ids_to_delete)} 条旧记录')
    
    # 4. 生成向量
    encoder = EmbeddingEncoder()
    texts = [c.get('content', '') for c in chunks]
    vectors = encoder.encode_batch(texts)
    print(f'生成 {len(vectors)} 个向量')
    
    # 5. 插入新记录
    import time
    insert_data = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        insert_data.append({
            'document_id': doc_id,
            'team_id': new_team_id,
            'chunk_id': f'{doc_id}_{i}',
            'content': chunk.get('content', '')[:500],
            'embedding': vec,
            'metadata': {'chunk_index': i},
            'created_at': int(time.time())
        })
    
    client.insert('askme_documents', data=insert_data)
    print(f'已插入 {len(insert_data)} 条新记录')
    
    # 验证
    new_records = client.query(
        'askme_documents', 
        filter=f'document_id == "{doc_id}"', 
        output_fields=['document_id', 'team_id'],
        limit=10
    )
    print(f'验证: {new_records[0] if new_records else "无记录"}')

if __name__ == '__main__':
    # 修复徽商银行文档的team_id
    fix_team_id('doc_412c89043959', '研发部')
