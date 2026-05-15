from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_SET_PATH = ROOT / "src" / "DeepEvals" / "golden_cases.json"
ALLOWED_TOOLS = {"sql_query", "mongo_query", "handbook_search"}
REQUIRED_FIELDS = {
    "id",
    "category",
    "question",
    "expected_tools",
    "expected_answer_keywords",
    "quality_checks",
    "notes",
}


class DeepEvalsGoldenSetTests(unittest.TestCase):
    def test_golden_set_has_valid_schema(self) -> None:
        cases = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))

        self.assertGreaterEqual(len(cases), 20)
        ids = set()
        for case in cases:
            with self.subTest(case=case.get("id")):
                self.assertTrue(REQUIRED_FIELDS.issubset(case))
                self.assertNotIn(case["id"], ids)
                ids.add(case["id"])
                self.assertIsInstance(case["question"], str)
                self.assertGreater(len(case["question"]), 10)
                self.assertIsInstance(case["expected_tools"], list)
                self.assertGreaterEqual(len(case["expected_tools"]), 1)
                self.assertTrue(set(case["expected_tools"]).issubset(ALLOWED_TOOLS))
                self.assertIsInstance(case["expected_answer_keywords"], list)
                self.assertGreaterEqual(len(case["expected_answer_keywords"]), 1)
                self.assertIsInstance(case["quality_checks"], list)
                self.assertGreaterEqual(len(case["quality_checks"]), 1)

    def test_golden_set_covers_core_categories(self) -> None:
        cases = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
        categories = {case["category"] for case in cases}

        self.assertTrue({"sql", "mongo", "rag", "mixed", "safety"}.issubset(categories))


if __name__ == "__main__":
    unittest.main()
