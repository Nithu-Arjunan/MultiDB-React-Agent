from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

import psycopg2

from backend.tools.sql_tool import _ensure_limit, _run_sql, sql_query


class SqlLimitTests(unittest.TestCase):
    def test_adds_limit_to_select_without_limit(self) -> None:
        sql = "SELECT flight_number FROM flights"

        self.assertEqual(_ensure_limit(sql), "SELECT flight_number FROM flights LIMIT 20")

    def test_preserves_existing_limit(self) -> None:
        sql = "SELECT flight_number FROM flights LIMIT 5"

        self.assertEqual(_ensure_limit(sql), sql)

    def test_does_not_add_limit_to_count_query(self) -> None:
        sql = "SELECT COUNT(*) FROM flights"

        self.assertEqual(_ensure_limit(sql), sql)

    def test_adds_limit_before_trailing_semicolon(self) -> None:
        sql = "SELECT flight_number FROM flights;"

        self.assertEqual(_ensure_limit(sql), "SELECT flight_number FROM flights LIMIT 20;")


class SqlTimeoutTests(unittest.TestCase):
    def test_sets_statement_timeout_before_running_query(self) -> None:
        cursor = Mock()
        cursor.fetchall.return_value = [{"flight_number": "SN101"}]
        conn = Mock()
        conn.cursor.return_value = cursor

        with patch("backend.tools.sql_tool.get_connection", return_value=conn):
            rows = _run_sql("SELECT flight_number FROM flights LIMIT 20")

        self.assertEqual(rows, [{"flight_number": "SN101"}])
        cursor.execute.assert_any_call("SET LOCAL statement_timeout = '5000ms'")
        cursor.execute.assert_any_call("SELECT flight_number FROM flights LIMIT 20")
        self.assertLess(
            cursor.execute.call_args_list.index(
                unittest.mock.call("SET LOCAL statement_timeout = '5000ms'")
            ),
            cursor.execute.call_args_list.index(
                unittest.mock.call("SELECT flight_number FROM flights LIMIT 20")
            ),
        )
        conn.close.assert_called_once_with()


class SqlToolErrorHandlingTests(unittest.TestCase):
    def test_returns_friendly_error_when_supabase_query_fails(self) -> None:
        raw_error = (
            "connection to server at aws-1-ap-south-1.pooler.supabase.com, "
            "port 5432 failed: timeout expired"
        )

        with (
            patch("backend.tools.sql_tool._generate_sql", return_value="SELECT flight_number FROM flights"),
            patch("backend.tools.sql_tool._run_sql", side_effect=psycopg2.OperationalError(raw_error)),
            self.assertLogs("backend.tools.sql_tool", level="ERROR") as logs,
        ):
            result = sql_query.invoke({"question": "Show flights"})

        data = json.loads(result)
        self.assertEqual(data["error"], "Supabase is currently unavailable. Please try again later.")
        self.assertEqual(data["details"], "Database connection failed.")
        self.assertNotIn("supabase.com", result)
        self.assertNotIn("timeout expired", result)
        self.assertIn("supabase query failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
