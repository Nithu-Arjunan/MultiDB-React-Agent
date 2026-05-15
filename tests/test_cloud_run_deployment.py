from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CloudRunDeploymentTests(unittest.TestCase):
    def test_dockerfile_builds_frontend_and_runs_fastapi_on_cloud_run_port(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("FROM node:", dockerfile)
        self.assertIn("npm ci", dockerfile)
        self.assertIn("npm run build", dockerfile)
        self.assertIn("FROM python:", dockerfile)
        self.assertIn("uvicorn", dockerfile)
        self.assertIn("backend.main:app", dockerfile)
        self.assertIn("${PORT:-8080}", dockerfile)
        self.assertIn("PYTHONPATH=/app/src", dockerfile)

    def test_dockerignore_excludes_local_secrets_and_generated_artifacts(self) -> None:
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

        expected_patterns = [
            "src/.env",
            ".env",
            ".venv/",
            "src/frontend/node_modules/",
            "src/frontend/dist/",
            "src/DeepEvals/results/",
            "__pycache__/",
            ".git/",
        ]

        for pattern in expected_patterns:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, dockerignore)


if __name__ == "__main__":
    unittest.main()
