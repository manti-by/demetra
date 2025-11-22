from pathlib import Path

def load_prompt(name: str) -> str:
    return Path(f"prompts/{name}.md").read_text()
