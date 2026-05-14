from __future__ import annotations

import unittest
from pathlib import Path

from backend.main import get_frontend_dist_path


class FrontendServingTests(unittest.TestCase):
    def test_frontend_dist_path_points_to_project_frontend(self) -> None:
        expected = Path(__file__).resolve().parents[1] / "src" / "frontend" / "dist"

        self.assertEqual(get_frontend_dist_path(), expected)


if __name__ == "__main__":
    unittest.main()
