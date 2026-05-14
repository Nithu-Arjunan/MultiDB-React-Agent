from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BackendImportTests(unittest.TestCase):
    def test_backend_main_runs_as_direct_script(self) -> None:
        result = subprocess.run(
            [sys.executable, "src/backend/main.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backend_main_imports_with_src_on_pythonpath(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"

        result = subprocess.run(
            [sys.executable, "-c", "import backend.main"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backend_package_imports_from_project_root(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import backend"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
