from typing import Any, Dict
import json

def load_json(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return json.load(f)
