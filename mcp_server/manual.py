import json
import os

_MANUAL_DIR = os.path.join(os.path.dirname(__file__), "..", "manual")
_INDEX_PATH = os.path.join(_MANUAL_DIR, "index.json")


def get_index() -> list[str]:
    if not os.path.exists(_INDEX_PATH):
        return []
    with open(_INDEX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return list(data.keys())


def get_entry(name: str) -> str | None:
    if not os.path.exists(_INDEX_PATH):
        return None
    with open(_INDEX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get(name)


def search(keyword: str) -> str:
    if not os.path.exists(_INDEX_PATH):
        return "(Manual index not yet available)"
    with open(_INDEX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    kw = keyword.lower()
    results = []
    for class_name, content in data.items():
        hits = [line.strip() for line in content.splitlines() if kw in line.lower()]
        if hits:
            results.append(f"## {class_name}")
            results.extend(hits[:10])
            if len(hits) > 10:
                results.append(f"  ... ({len(hits) - 10} more lines)")
    if not results:
        return f"No results for '{keyword}'."
    return "\n".join(results)
