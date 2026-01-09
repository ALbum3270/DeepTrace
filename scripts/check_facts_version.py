"""Check facts_index_v2 doc_version_id binding."""
import json
from pathlib import Path

# 找一个文档的 facts_index_v2
base = Path('artifacts/phase1')
doc_dirs = [d for d in base.iterdir() if d.is_dir() and 'e1e155b3' in d.name and '_' in d.name]
if doc_dirs:
    f = doc_dirs[0] / 'facts_index_v2.json'
    d = json.loads(f.read_text(encoding='utf-8'))
    items = d.get('items', [])
    print(f'facts_index_v2 items count: {len(items)}')
    if items:
        item = items[0]
        ref = item.get('doc_ref', {})
        print(f'\nFirst item doc_ref:')
        print(f'  doc_id: {ref.get("doc_id")}')
        doc_key = ref.get('doc_key', '')
        print(f'  doc_key: {doc_key[:50] if doc_key else "N/A"}...')
        vid = ref.get('doc_version_id', '')
        print(f'  doc_version_id: {vid[:16] if vid else "N/A"}...')
        print(f'  evidence_quote length: {len(ref.get("evidence_quote",""))}')
