from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path


def prepare_workspace_tmp_dir(prefix: str) -> Path:
    root = Path.cwd() / ".tmp-tests"
    root.mkdir(parents=True, exist_ok=True)
    temp_dir = root / f"{prefix}-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    (root / f"LATEST-{prefix}.txt").write_text(str(temp_dir), encoding="utf-8")

    for child in root.iterdir():
        if child == temp_dir or child.name == f"LATEST-{prefix}.txt":
            continue
        if child.is_dir():
            _remove_path_with_retries(child, required=False)
        else:
            child.unlink(missing_ok=True)

    return temp_dir


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
