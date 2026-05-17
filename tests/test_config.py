from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_settings_read_environment_values(self) -> None:
        from config import settings

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai-key",
                "SUPABASE_URI": "postgresql://example",
                "MONGO_URI": "mongodb://example",
                "GOOGLE_CLIENT_ID": "google-client-id",
                "JWT_SECRET_KEY": "jwt-secret",
                "JWT_EXPIRE_MINUTES": "45",
                "ALLOWED_ORIGINS": "http://127.0.0.1:8010,https://example.run.app",
            },
            clear=False,
        ):
            self.assertEqual(settings.openai_api_key, "test-openai-key")
            self.assertEqual(settings.supabase_uri, "postgresql://example")
            self.assertEqual(settings.mongo_uri, "mongodb://example")
            self.assertEqual(settings.google_client_id, "google-client-id")
            self.assertEqual(settings.jwt_secret_key, "jwt-secret")
            self.assertEqual(settings.jwt_expire_minutes, 45)
            self.assertEqual(
                settings.allowed_origins,
                ["http://127.0.0.1:8010", "https://example.run.app"],
            )

    def test_runtime_code_uses_config_instead_of_direct_environ_access(self) -> None:
        allowed = {
            ROOT / "src" / "config.py",
        }
        offenders = []

        for path in (ROOT / "src").rglob("*.py"):
            if path in allowed or "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if "os.environ" in source or "os.getenv" in source or "load_dotenv" in source:
                offenders.append(path.relative_to(ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_config_import_does_not_emit_secret_debug_output(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "OPENAI_API_KEY": "test-openai-key",
                "SUPABASE_URI": "postgresql://example",
                "MONGO_URI": "mongodb://example",
                "GOOGLE_CLIENT_ID": "google-client-id",
                "JWT_SECRET_KEY": "jwt-secret",
            }
        )

        result = subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_default_allowed_origins_include_cloud_run_url(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "OPENAI_API_KEY": "test-openai-key",
                "SUPABASE_URI": "postgresql://example",
                "MONGO_URI": "mongodb://example",
                "GOOGLE_CLIENT_ID": "google-client-id",
                "JWT_SECRET_KEY": "jwt-secret",
            }
        )
        env.pop("ALLOWED_ORIGINS", None)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from config import settings; print('\\n'.join(settings.allowed_origins))",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "https://multi-db-react-agent-259390522728.us-central1.run.app",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
