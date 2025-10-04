import json
import os

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

def load_snapshot(name: str):
    path = os.path.join(SNAPSHOT_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_snapshot(name: str, data: dict):
    path = os.path.join(SNAPSHOT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def assert_match_snapshot(name: str, key: str, value: dict, update: bool = False):
    """
    name: snapshot file name (without .json)
    key: test case identifier
    value: snapshot data (dict)
    update: True → overwrite snapshot
    """
    snapshots = load_snapshot(name)
    if update or key not in snapshots:
        snapshots[key] = value
        save_snapshot(name, snapshots)
        return

    assert snapshots[key] == value, f"Snapshot mismatch for {key}:\nexpected={snapshots[key]}\nactual={value}"
