import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import runtime_paths


class TestRuntimePaths(unittest.TestCase):
    def test_bundled_resource_path_uses_project_root_when_not_frozen(self):
        resource_path = runtime_paths.bundled_resource_path("data", "projects.json")

        self.assertEqual(resource_path, Path("data/projects.json").resolve())

    def test_user_data_dir_uses_xdg_data_home_on_linux(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"XDG_DATA_HOME": tmpdir}, clear=False):
                with patch.object(sys, "platform", "linux"):
                    self.assertEqual(
                        runtime_paths.user_data_dir(),
                        Path(tmpdir) / runtime_paths.APP_DIR_NAME,
                    )

    def test_user_log_dir_uses_localappdata_on_windows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}, clear=False):
                with patch.object(sys, "platform", "win32"):
                    self.assertEqual(
                        runtime_paths.user_log_dir(),
                        Path(tmpdir) / runtime_paths.APP_NAME / "Logs",
                    )

    def test_ensure_runtime_dirs_creates_expected_directories(self):
        with tempfile.TemporaryDirectory() as data_dir, tempfile.TemporaryDirectory() as state_dir:
            with patch.dict(
                os.environ,
                {"XDG_DATA_HOME": data_dir, "XDG_STATE_HOME": state_dir},
                clear=False,
            ):
                with patch.object(sys, "platform", "linux"):
                    runtime_paths.ensure_runtime_dirs()

                    self.assertTrue(runtime_paths.user_data_dir().exists())
                    self.assertTrue(runtime_paths.user_log_dir().exists())


if __name__ == "__main__":
    unittest.main()
