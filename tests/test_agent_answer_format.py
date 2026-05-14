from __future__ import annotations

import unittest

from backend.agent import TOOL_ROUTING_HINT


class AgentAnswerFormatTests(unittest.TestCase):
    def test_prompt_requests_user_friendly_final_answers(self) -> None:
        self.assertIn("user-friendly", TOOL_ROUTING_HINT)
        self.assertIn("Do not expose raw JSON", TOOL_ROUTING_HINT)
        self.assertIn("bullet", TOOL_ROUTING_HINT.lower())


if __name__ == "__main__":
    unittest.main()
