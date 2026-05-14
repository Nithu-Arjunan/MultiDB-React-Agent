from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from backend.tools.sql_tool import _ensure_limit, _run_sql


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


if __name__ == "__main__":
    unittest.main()
