from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.DeepEvals.run_golden_eval import (
    build_case_result,
    extract_tool_calls,
    write_report,
)


class RunGoldenEvalTests(unittest.TestCase):
    def test_extract_tool_calls_from_agent_result(self) -> None:
        result = {
            "intermediate_steps": [
                (SimpleNamespace(tool="sql_query", tool_input={"question": "Flights"}), "{}"),
                (SimpleNamespace(tool="handbook_search", tool_input="refund"), "policy"),
            ]
        }

        self.assertEqual(
            extract_tool_calls(result),
            [
                {"tool": "sql_query", "input": {"question": "Flights"}, "output": "{}"},
                {"tool": "handbook_search", "input": "refund", "output": "policy"},
            ],
        )

    def test_build_case_result_scores_tools_and_keywords(self) -> None:
        case = {
            "id": "sql_001",
            "category": "sql",
            "question": "Show delayed flights",
            "expected_tools": ["sql_query"],
            "expected_answer_keywords": ["delayed", "flight"],
            "quality_checks": ["answer_relevancy", "tool_routing"],
            "notes": "test",
        }
        agent_result = {
            "output": "There are two delayed flights.",
            "intermediate_steps": [
                (SimpleNamespace(tool="sql_query", tool_input={"question": "Show delayed flights"}), "rows")
            ],
        }

        result = build_case_result(case, agent_result, elapsed_ms=123)

        self.assertTrue(result["passed"])
        self.assertEqual(result["actual_tools"], ["sql_query"])
        self.assertEqual(result["missing_tools"], [])
        self.assertEqual(result["unexpected_tools"], [])
        self.assertEqual(result["missing_keywords"], [])
        self.assertEqual(result["elapsed_ms"], 123)

    def test_write_report_creates_latest_and_timestamped_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = {
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "results": [{"id": "sql_001", "passed": True}],
            }

            latest_path = write_report(report, Path(tmp))

            self.assertEqual(latest_path, Path(tmp) / "latest_eval_results.json")
            self.assertTrue(latest_path.exists())
            self.assertEqual(json.loads(latest_path.read_text(encoding="utf-8")), report)
            timestamped = list(Path(tmp).glob("eval_results_*.json"))
            self.assertEqual(len(timestamped), 1)


if __name__ == "__main__":
    unittest.main()
