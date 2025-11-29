import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

print("Attempting to import src.agents.comment_extractor...")
try:
    from src.agents.comment_extractor import extract_comments_from_article
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()

print("\nAttempting to import src.core.models.evidence...")
try:
    from src.core.models.evidence import Evidence, EvidenceType
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
