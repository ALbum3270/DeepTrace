import sys
import os

sys.path.append(os.getcwd())

try:
    from src.core.models.evidence import Evidence, EvidenceType
    print("Evidence import successful")
    e = Evidence(title="Test", content="Content", url="http://test.com", source="news", type=EvidenceType.ARTICLE)
    print(f"Evidence created: {e}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
