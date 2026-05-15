from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.auth import create_access_token, verify_access_token
from backend.main import app


class AuthTokenTests(unittest.TestCase):
    def test_access_token_round_trip(self) -> None:
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-with-at-least-32-bytes"}, clear=False):
            token = create_access_token({"sub": "google-user-1", "email": "user@example.com"})

            payload = verify_access_token(token)

        self.assertEqual(payload["sub"], "google-user-1")
        self.assertEqual(payload["email"], "user@example.com")


class AuthEndpointTests(unittest.TestCase):
    def test_chat_rejects_missing_bearer_token(self) -> None:
        client = TestClient(app)

        response = client.post("/chat", json={"question": "Show flights"})

        self.assertEqual(response.status_code, 401)

    def test_google_login_returns_app_jwt(self) -> None:
        client = TestClient(app)
        google_user = {
            "sub": "google-user-1",
            "email": "user@example.com",
            "name": "Example User",
            "picture": "https://example.com/avatar.png",
        }

        with (
            patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-with-at-least-32-bytes"}, clear=False),
            patch("backend.main.verify_google_id_token", return_value=google_user),
        ):
            response = client.post("/auth/google", json={"credential": "google-id-token"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["email"], "user@example.com")
        self.assertTrue(data["access_token"])


if __name__ == "__main__":
    unittest.main()
