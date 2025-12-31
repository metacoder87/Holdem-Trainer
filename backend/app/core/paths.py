from pathlib import Path
import os
import sys


def ensure_src_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    src_path = root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    return root


def get_project_root() -> Path:
    return ensure_src_path()


def get_data_file() -> Path:
    override = os.getenv("PYHOLDEM_DATA_FILE")
    if override:
        return Path(override)
    return get_project_root() / "data" / "players.json"
