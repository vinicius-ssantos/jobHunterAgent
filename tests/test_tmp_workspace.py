from __future__ import annotations

import shutil
import time
import unittest
from pathlib import Path

from tests.tmp_workspace import prepare_workspace_tmp_dir


class WorkspaceTmpDirTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(Path.cwd() / ".tmp-tests", ignore_errors=True)

    def test_prepare_workspace_tmp_dir_prunes_only_older_same_prefix_directories(self) -> None:
        root = Path.cwd() / ".tmp-tests"
        root.mkdir(parents=True, exist_ok=True)
        prefix = "tmp-workspace-test"
        for suffix in ("old-a", "old-b", "old-c"):
            path = root / f"{prefix}-{suffix}"
            path.mkdir(parents=True, exist_ok=True)
            time.sleep(0.01)

        created = prepare_workspace_tmp_dir(prefix)

        remaining_dirs = sorted(path.name for path in root.iterdir() if path.is_dir() and path.name.startswith(prefix))
        self.assertIn(created.name, remaining_dirs)
        self.assertEqual(len(remaining_dirs), 3)
        self.assertNotIn(f"{prefix}-old-a", remaining_dirs)

    def test_prepare_workspace_tmp_dir_preserves_other_prefix_directories(self) -> None:
        root = Path.cwd() / ".tmp-tests"
        root.mkdir(parents=True, exist_ok=True)
        preserved = root / "other-prefix-dir"
        preserved.mkdir(parents=True, exist_ok=True)

        prepare_workspace_tmp_dir("tmp-workspace-test")

        self.assertTrue(preserved.exists())
