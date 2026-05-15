from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendContentTests(unittest.TestCase):
    def test_chat_heading_uses_full_product_name(self) -> None:
        source = (ROOT / "src" / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")

        self.assertIn("Multi DB React Agent", source)

    def test_primary_buttons_use_blue_or_green_not_orange(self) -> None:
        styles = (ROOT / "src" / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertNotIn("#c75f2a", styles)
        self.assertRegex(styles, r"background:\s*#(1d5b74|16724a|0f766e)")

    def test_frontend_uses_streaming_chat_endpoint(self) -> None:
        source = (ROOT / "src" / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")

        self.assertIn('fetch("/chat/stream"', source)
        self.assertIn("Agent trace", source)

    def test_frontend_uses_google_auth_and_bearer_token(self) -> None:
        source = (ROOT / "src" / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")
        index = (ROOT / "src" / "frontend" / "index.html").read_text(encoding="utf-8")

        self.assertIn('fetch("/auth/google"', source)
        self.assertIn("Authorization", source)
        self.assertIn("skynova-auth-token", source)
        self.assertIn("https://accounts.google.com/gsi/client", index)

    def test_frontend_can_render_markdown_table_answers_as_user_friendly_cards(self) -> None:
        source = (ROOT / "src" / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")

        self.assertIn("formatMarkdownTableAnswer", source)
        self.assertIn("answer-card-grid", source)


if __name__ == "__main__":
    unittest.main()
