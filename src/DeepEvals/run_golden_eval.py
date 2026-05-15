from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

load_dotenv(SRC_ROOT / ".env")

from backend.agent import build_agent  # noqa: E402


GOLDEN_SET_PATH = Path(__file__).with_name("golden_cases.json")
RESULTS_DIR = Path(__file__).with_name("results")


def load_cases(path: Path = GOLDEN_SET_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_tool_calls(agent_result: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls = []
    for action, observation in agent_result.get("intermediate_steps", []):
        tool_calls.append(
            {
                "tool": action.tool,
                "input": action.tool_input,
                "output": str(observation),
            }
        )
    return tool_calls


def build_case_result(
    case: dict[str, Any],
    agent_result: dict[str, Any],
    elapsed_ms: int,
) -> dict[str, Any]:
    answer = str(agent_result.get("output", ""))
    tool_calls = extract_tool_calls(agent_result)
    actual_tools = [call["tool"] for call in tool_calls]
    expected_tools = list(case["expected_tools"])
    expected_keywords = list(case["expected_answer_keywords"])

    missing_tools = [tool for tool in expected_tools if tool not in actual_tools]
    unexpected_tools = [tool for tool in actual_tools if tool not in expected_tools]
    lower_answer = answer.lower()
    missing_keywords = [
        keyword
        for keyword in expected_keywords
        if keyword.lower() not in lower_answer
    ]

    passed = not missing_tools and not unexpected_tools and not missing_keywords and bool(answer.strip())

    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "passed": passed,
        "expected_tools": expected_tools,
        "actual_tools": actual_tools,
        "missing_tools": missing_tools,
        "unexpected_tools": unexpected_tools,
        "expected_answer_keywords": expected_keywords,
        "missing_keywords": missing_keywords,
        "answer": answer,
        "tool_calls": tool_calls,
        "elapsed_ms": elapsed_ms,
        "quality_checks": case.get("quality_checks", []),
        "notes": case.get("notes", ""),
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(results), 3) if results else 0,
    }


def write_report(report: dict[str, Any], results_dir: Path = RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    latest_path = results_dir / "latest_eval_results.json"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamped_path = results_dir / f"eval_results_{timestamp}.json"
    serialized = json.dumps(report, indent=2, default=str)

    latest_path.write_text(serialized + "\n", encoding="utf-8")
    timestamped_path.write_text(serialized + "\n", encoding="utf-8")
    return latest_path


def run_golden_eval(
    cases_path: Path = GOLDEN_SET_PATH,
    results_dir: Path = RESULTS_DIR,
    limit: int | None = None,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    if limit is not None:
        cases = cases[:limit]

    if not cases:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cases_path": str(cases_path),
            "summary": summarize_results([]),
            "results": [],
        }
        report["report_path"] = str(write_report(report, results_dir))
        return report

    agent = build_agent()
    results = []
    for case in cases:
        start = time.monotonic()
        try:
            agent_result = agent.invoke({"input": case["question"]})
            elapsed_ms = int((time.monotonic() - start) * 1000)
            result = build_case_result(case, agent_result, elapsed_ms)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            result = {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "passed": False,
                "expected_tools": case["expected_tools"],
                "actual_tools": [],
                "missing_tools": case["expected_tools"],
                "unexpected_tools": [],
                "expected_answer_keywords": case["expected_answer_keywords"],
                "missing_keywords": case["expected_answer_keywords"],
                "answer": "",
                "tool_calls": [],
                "elapsed_ms": elapsed_ms,
                "quality_checks": case.get("quality_checks", []),
                "notes": case.get("notes", ""),
                "error": str(exc),
            }
        results.append(result)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases_path": str(cases_path),
        "summary": summarize_results(results),
        "results": results,
    }
    report["report_path"] = str(write_report(report, results_dir))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local golden-set evals.")
    parser.add_argument("--cases", type=Path, default=GOLDEN_SET_PATH)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = run_golden_eval(args.cases, args.results_dir, args.limit)
    summary = report["summary"]
    print(
        f"Golden eval complete: {summary['passed']}/{summary['total']} passed "
        f"({summary['failed']} failed)."
    )
    print(f"Report written to: {report['report_path']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
