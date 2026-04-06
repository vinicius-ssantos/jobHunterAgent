from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

_RECENT_DIRS_TO_KEEP = 2


def prepare_workspace_tmp_dir(prefix: str) -> Path:
    root = Path.cwd() / ".tmp-tests"
    root.mkdir(parents=True, exist_ok=True)
    temp_dir = root / f"{prefix}-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    (root / f"LATEST-{prefix}.txt").write_text(str(temp_dir), encoding="utf-8")

    _prune_prefix_entries(root, prefix=prefix, current_temp_dir=temp_dir)

    return temp_dir


def _prune_prefix_entries(root: Path, *, prefix: str, current_temp_dir: Path) -> None:
    latest_marker = root / f"LATEST-{prefix}.txt"
    candidate_dirs = [
        child
        for child in root.iterdir()
        if child.is_dir() and child != current_temp_dir and child.name.startswith(f"{prefix}-")
    ]
    candidate_dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)

    for child in candidate_dirs[_RECENT_DIRS_TO_KEEP:]:
        _remove_path_with_retries(child, required=False)

    for child in root.iterdir():
        if child == latest_marker:
            continue
        if child.is_file() and child.name.startswith(f"LATEST-{prefix}"):
            child.unlink(missing_ok=True)


def _remove_path_with_retries(
    path: Path,
    *,
    required: bool,
    attempts: int = 20,
    delay_seconds: float = 0.05,
) -> bool:
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt == attempts - 1:
                if required:
                    raise
                return False
            time.sleep(delay_seconds)
    return False
