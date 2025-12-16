
import sys
import os
# Add src to path
sys.path.append(os.getcwd())

from unittest.mock import Mock
from src.infrastructure.utils.verification import verify_report

def run_test():
    print("Running test_removes_fake_links logic...")
    # Mock evidences
    mock_ev = Mock()
    mock_ev.url = "https://real-url.com/article"
    evidences = [mock_ev]
    
    report = """
    Check this [real link](https://real-url.com/article) and 
    this [fake link](https://fake-url.com/bogus).
    """
    
    try:
        result, stats = verify_report(report, evidences)
        print("Success!")
        print(f"Result len: {len(result)}")
        print(f"Stats: {stats}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
