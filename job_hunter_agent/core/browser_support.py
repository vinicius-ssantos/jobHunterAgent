from __future__ import annotations

import json
import os
from pathlib import Path


def resolve_local_chromium() -> Path:
    browsers_root = Path(os.getenv("PLAYWRIGHT_BROWSERS_PATH", ".playwright-browsers")).resolve()
    candidates = sorted(browsers_root.rglob("chrome.exe"))
    if not candidates:
        raise RuntimeError(
            "Nenhum chrome.exe do Playwright foi encontrado. Configure PLAYWRIGHT_BROWSERS_PATH e rode playwright install chromium."
        )
    return candidates[0]


def load_playwright_storage_state(path: str | Path) -> dict:
    state = json.loads(Path(path).read_text(encoding="utf-8"))
    sanitized_cookies: list[dict] = []
    for cookie in state.get("cookies", []):
        sanitized = dict(cookie)
        partition_key = sanitized.get("partitionKey")
        if isinstance(partition_key, dict):
            top_level_site = partition_key.get("topLevelSite")
            if isinstance(top_level_site, str) and top_level_site.strip():
                sanitized["partitionKey"] = top_level_site
            else:
                sanitized.pop("partitionKey", None)
        elif partition_key is not None and not isinstance(partition_key, str):
            sanitized.pop("partitionKey", None)
        sanitized_cookies.append(sanitized)
    state["cookies"] = sanitized_cookies
    return state


def build_available_file_paths(base_dir: Path, limit: int = 20) -> list[str]:
    paths: list[str] = []
    for index in range(1, limit + 1):
        relative = f"./screenshot{index}.png"
        absolute = (base_dir / f"screenshot{index}.png").resolve()
        paths.append(relative)
        paths.append(str(absolute))
    return paths


def automation_result_to_text(result: object) -> str:
    if isinstance(result, str):
        return result

    final_result = getattr(result, "final_result", None)
    if callable(final_result):
        extracted = final_result()
        if isinstance(extracted, str):
            return extracted

    return str(result)


def extract_json_object(result: object) -> dict:
    result_text = automation_result_to_text(result)
    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    if start == -1 or end <= start:
        return {}
    try:
        return json.loads(result_text[start:end])
    except json.JSONDecodeError:
        return {}
