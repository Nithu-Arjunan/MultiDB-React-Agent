from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from backend.agent import stream_events_from_result
from backend.main import format_sse


class StreamingTests(unittest.TestCase):
    def test_stream_events_include_action_observation_answer_and_done(self) -> None:
        result = {
            "output": "Flight SN101 is scheduled.",
            "intermediate_steps": [
                (
                    SimpleNamespace(tool="sql_query", tool_input={"question": "Show SN101"}),
                    '{"row_count": 1, "data": [{"flight_number": "SN101"}]}',
                )
            ],
        }

        events = list(stream_events_from_result(result, elapsed_ms=42))

        self.assertEqual(
            events,
            [
                {
                    "type": "action",
                    "tool": "sql_query",
                    "input": {"question": "Show SN101"},
                },
                {
                    "type": "observation",
                    "tool": "sql_query",
                    "output": '{"row_count": 1, "data": [{"flight_number": "SN101"}]}',
                },
                {"type": "answer", "answer": "Flight SN101 is scheduled."},
                {"type": "done", "elapsed_ms": 42},
            ],
        )

    def test_format_sse_serializes_named_json_event(self) -> None:
        event = format_sse("action", {"tool": "sql_query"})

        self.assertEqual(event, 'event: action\ndata: {"tool": "sql_query"}\n\n')
        payload = event.split("data: ", 1)[1].strip()
        self.assertEqual(json.loads(payload), {"tool": "sql_query"})


if __name__ == "__main__":
    unittest.main()
