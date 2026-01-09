"""Check Phase2 CDC artifacts from latest run."""
import json
from pathlib import Path

base = Path('artifacts/phase1')
run_dirs = [d for d in base.iterdir() if d.is_dir() and '_' not in d.name]
if run_dirs:
    latest = sorted(run_dirs, key=lambda d: d.stat().st_mtime)[-1]
    print(f'Latest run: {latest.name}')
    
    # 检查 doc_versions_summary.json
    dvs_path = latest / 'doc_versions_summary.json'
    if dvs_path.exists():
        dvs = json.loads(dvs_path.read_text(encoding='utf-8'))
        print(f"\nDoc Versions Summary:")
        print(f"  run_id: {dvs.get('run_id')}")
        s = dvs.get('summary', {})
        print(f"  docs_total: {s.get('docs_total')}")
        print(f"  docs_first_seen: {s.get('docs_first_seen')}")
        print(f"  docs_unchanged: {s.get('docs_unchanged')}")
        print(f"  docs_changed: {s.get('docs_changed')}")
        # 显示前3个文档的 drift_status
        docs = dvs.get('documents', [])
        print(f"\n  Sample documents ({len(docs)} total):")
        for d in docs[:3]:
            print(f"    {d.get('doc_id')}: {d.get('drift_status')}")
    else:
        print('doc_versions_summary.json not found')
    
    # 检查 metrics_summary.json
    ms_path = latest / 'metrics_summary.json'
    if ms_path.exists():
        ms = json.loads(ms_path.read_text(encoding='utf-8'))
        print(f"\nMetrics Summary:")
        print(f"  key_claim_locatable_rate: {ms.get('key_claim_locatable_rate')}")
        print(f"  locatable_rate_overall: {ms.get('locatable_rate_overall')}")
        print(f"  reason_counts: {ms.get('reason_counts')}")
else:
    print('No run directories found')
