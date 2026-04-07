import json
import shutil
import unittest
from unittest.mock import patch

from job_hunter_agent.core.runtime import RuntimeGuard, is_project_browser_process, is_project_python_process
from tests.tmp_workspace import prepare_workspace_tmp_dir


class FakeProcess:
    def __init__(
        self,
        *,
        pid: int,
        name: str = "python.exe",
        cwd: str | None = None,
        cmdline: list[str] | None = None,
    ) -> None:
        self.pid = pid
        self.info = {"name": name, "cmdline": cmdline or []}
        self._cwd = cwd

    def name(self) -> str:
        return self.info["name"]

    def cwd(self) -> str:
        if self._cwd is None:
            raise FileNotFoundError
        return self._cwd

    def cmdline(self) -> list[str]:
        return self.info["cmdline"]


class FakePsutilProcessWithoutInfo:
    def __init__(self, *, pid: int, name: str = "python.exe", cwd: str | None = None, cmdline: list[str] | None = None) -> None:
        self.pid = pid
        self._name = name
        self._cwd = cwd
        self._cmdline = cmdline or []

    def name(self) -> str:
        return self._name

    def cwd(self) -> str:
        if self._cwd is None:
            raise FileNotFoundError
        return self._cwd

    def cmdline(self) -> list[str]:
        return self._cmdline


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = prepare_workspace_tmp_dir("runtime")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_project_python_process_matches_project_cwd(self) -> None:
        process = FakeProcess(pid=1234, cwd=str(self.temp_dir))

        self.assertTrue(is_project_python_process(process, self.temp_dir.resolve(), current_pid=9999))

    def test_is_project_python_process_rejects_current_pid(self) -> None:
        process = FakeProcess(pid=1234, cwd=str(self.temp_dir))

        self.assertFalse(is_project_python_process(process, self.temp_dir.resolve(), current_pid=1234))

    def test_is_project_python_process_matches_main_py_in_command(self) -> None:
        process = FakeProcess(
            pid=1234,
            cwd="C:\\other",
            cmdline=["python", "main.py", "--agora"],
        )

        self.assertTrue(is_project_python_process(process, self.temp_dir.resolve(), current_pid=9999))

    def test_is_project_browser_process_matches_browser_use_profile(self) -> None:
        process = FakeProcess(
            pid=1234,
            name="chrome.exe",
            cwd="C:\\other",
            cmdline=[
                "chrome.exe",
                f"--user-data-dir={self.temp_dir.resolve()}\\.browseruse\\profiles\\job-hunter-agent",
            ],
        )

        self.assertTrue(is_project_browser_process(process, (self.temp_dir / ".browseruse").resolve()))

    def test_runtime_guard_writes_and_releases_lock_file(self) -> None:
        lock_path = self.temp_dir / "job_hunter_agent.lock"
        guard = RuntimeGuard(
            project_root=self.temp_dir.resolve(),
            browser_use_dir=(self.temp_dir / ".browseruse").resolve(),
            lock_path=lock_path,
            current_pid=4321,
        )
        guard._terminate_previous_locked_process = lambda: 0
        guard._terminate_project_browser_processes = lambda: 0

        terminated = guard.prepare_for_startup()

        self.assertEqual(terminated, 0)
        self.assertTrue(lock_path.exists())
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["pid"], 4321)

        guard.release()

        self.assertFalse(lock_path.exists())

    def test_runtime_guard_terminates_only_previous_locked_process(self) -> None:
        lock_path = self.temp_dir / "job_hunter_agent.lock"
        lock_path.write_text(
            json.dumps({"pid": 1234, "project_root": str(self.temp_dir.resolve())}),
            encoding="utf-8",
        )
        guard = RuntimeGuard(
            project_root=self.temp_dir.resolve(),
            browser_use_dir=(self.temp_dir / ".browseruse").resolve(),
            lock_path=lock_path,
            current_pid=4321,
        )
        fake_process = FakeProcess(pid=1234, cwd=str(self.temp_dir), cmdline=["python", "main.py"])
        terminated_calls: list[int] = []

        with patch("job_hunter_agent.runtime.psutil.Process", return_value=fake_process):
            guard._terminate_project_browser_processes = lambda: 0
            guard._terminate_process_tree = lambda process: terminated_calls.append(process.pid) or 1
            terminated = guard.prepare_for_startup()

        self.assertEqual(terminated, 1)
        self.assertEqual(terminated_calls, [1234])

    def test_is_project_python_process_supports_psutil_process_without_info(self) -> None:
        process = FakePsutilProcessWithoutInfo(
            pid=1234,
            cwd=str(self.temp_dir),
            cmdline=["python", "main.py", "--ciclos", "4"],
        )

        self.assertTrue(is_project_python_process(process, self.temp_dir.resolve(), current_pid=9999))
