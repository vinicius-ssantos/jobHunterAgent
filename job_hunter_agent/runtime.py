from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import psutil


logger = logging.getLogger(__name__)


def _process_info_value(process: psutil.Process, key: str):
    info = getattr(process, "info", None)
    if isinstance(info, dict):
        return info.get(key)
    return None


def is_project_python_process(process: psutil.Process, project_root: Path, current_pid: int) -> bool:
    if process.pid == current_pid:
        return False

    try:
        name = (_process_info_value(process, "name") or process.name()).lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

    if "python" not in name:
        return False

    try:
        cwd = process.cwd()
    except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
        cwd = None

    if cwd:
        try:
            if Path(cwd).resolve() == project_root:
                return True
        except OSError:
            pass

    try:
        cmdline = _process_info_value(process, "cmdline") or process.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        cmdline = []

    normalized_parts = [str(part).lower() for part in cmdline]
    project_root_text = str(project_root).lower()
    return any(
        project_root_text in part or part == "main.py" or part.endswith("\\main.py") or part.endswith("/main.py")
        for part in normalized_parts
    )


def iter_project_processes(project_root: Path, current_pid: int) -> list[psutil.Process]:
    matched: list[psutil.Process] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        if is_project_python_process(process, project_root, current_pid):
            matched.append(process)
    return matched


def is_project_browser_process(process: psutil.Process, browser_use_dir: Path) -> bool:
    try:
        name = (_process_info_value(process, "name") or process.name()).lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

    if not any(browser_name in name for browser_name in ("chrome", "chromium", "msedge")):
        return False

    try:
        cmdline = _process_info_value(process, "cmdline") or process.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

    normalized_parts = [str(part).lower() for part in cmdline]
    browser_use_text = str(browser_use_dir).lower()
    return any(
        browser_use_text in part or "browser-use-user-data-dir-" in part
        for part in normalized_parts
    )


def iter_project_browser_processes(browser_use_dir: Path) -> list[psutil.Process]:
    matched: list[psutil.Process] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        if is_project_browser_process(process, browser_use_dir):
            matched.append(process)
    return matched


@dataclass
class RuntimeGuard:
    project_root: Path
    browser_use_dir: Path
    lock_path: Path
    current_pid: int = os.getpid()

    def prepare_for_startup(self) -> int:
        terminated = self._terminate_previous_locked_process()
        terminated += self._terminate_project_browser_processes()
        self._write_lock_file()
        return terminated

    def release(self) -> None:
        if not self.lock_path.exists():
            return
        try:
            payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if payload.get("pid") == self.current_pid:
            self.lock_path.unlink(missing_ok=True)

    def _write_lock_file(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": self.current_pid,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "project_root": str(self.project_root),
        }
        self.lock_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _terminate_previous_locked_process(self) -> int:
        if not self.lock_path.exists():
            return 0

        try:
            payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.lock_path.unlink(missing_ok=True)
            return 0

        previous_pid = payload.get("pid")
        if not isinstance(previous_pid, int) or previous_pid == self.current_pid:
            return 0

        try:
            process = psutil.Process(previous_pid)
        except psutil.NoSuchProcess:
            self.lock_path.unlink(missing_ok=True)
            return 0

        if not is_project_python_process(process, self.project_root, self.current_pid):
            self.lock_path.unlink(missing_ok=True)
            return 0

        terminated_count = self._terminate_process_tree(process)
        if terminated_count:
            logger.info("Execucao anterior do projeto encerrada via lock file: %s", terminated_count)
        return terminated_count

    def _terminate_project_browser_processes(self) -> int:
        processes = iter_project_browser_processes(self.browser_use_dir)
        terminated_count = 0
        for process in processes:
            if self._terminate_process(process):
                terminated_count += 1
        if terminated_count:
            logger.info("Processos de navegador do projeto encerrados: %s", terminated_count)
        return terminated_count

    def _terminate_process_tree(self, process: psutil.Process) -> int:
        count = 0
        children: Iterable[psutil.Process]
        try:
            children = process.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            children = []

        for child in reversed(list(children)):
            if self._terminate_process(child):
                count += 1
        if self._terminate_process(process):
            count += 1
        return count

    @staticmethod
    def _terminate_process(process: psutil.Process) -> bool:
        try:
            process.terminate()
            process.wait(timeout=5)
            return True
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
