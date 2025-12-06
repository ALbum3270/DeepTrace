import json
import re
from typing import Dict, Optional, Any

def decamelize(data: Any) -> Any:
    """
    Simple implementation to convert camelCase to snake_case for keys in dicts.
    """
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            new_k = re.sub(r'(?<!^)(?=[A-Z])', '_', k).lower()
            new_dict[new_k] = decamelize(v)
        return new_dict
    elif isinstance(data, list):
        return [decamelize(item) for item in data]
    else:
        return data

class XiaoHongShuExtractor:
    def __init__(self):
        pass

    def extract_note_detail_from_html(self, note_id: str, html: str) -> Optional[Dict]:
        if "noteDetailMap" not in html:
            return None

        state_match = re.findall(r"window.__INITIAL_STATE__=({.*})</script>", html)
        if not state_match:
            return None
            
        state = state_match[0].replace("undefined", '""')
        if state != "{}":
            try:
                state_json = json.loads(state)
                # Use custom decamelize instead of humps
                note_dict = decamelize(state_json)
                return note_dict["note"]["note_detail_map"][note_id]["note"]
            except Exception:
                return None
        return None

    def extract_creator_info_from_html(self, html: str) -> Optional[Dict]:
        match = re.search(
            r"<script>window.__INITIAL_STATE__=(.+)<\/script>", html, re.M
        )
        if match is None:
            return None
        try:
            info = json.loads(match.group(1).replace(":undefined", ":null"), strict=False)
            if info is None:
                return None
            return info.get("user").get("userPageData")
        except Exception:
            return None
