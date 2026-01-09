"""Check example CDC record."""
import json
from pathlib import Path

p = list(Path('data/doc_versions').glob('*.json'))[0]
d = json.loads(p.read_text(encoding='utf-8'))
print('Example CDC record:')
doc_key = d.get('doc_key', '')
print(f'  doc_key: {doc_key[:60]}...')
vid = d.get('latest_doc_version_id', '')
print(f'  latest_doc_version_id: {vid[:16]}...')
print(f'  versions count: {len(d.get("versions",[]))}')
v = d.get('versions', [])[0] if d.get('versions') else {}
print(f'  first version seen_runs: {v.get("seen_runs",[])}')
print(f'  first_seen: {v.get("first_seen")}')
print(f'  last_seen: {v.get("last_seen")}')
