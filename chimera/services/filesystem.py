from pathlib import Path

def validate_project(path: str) -> bool:
    return Path(path).exists()
