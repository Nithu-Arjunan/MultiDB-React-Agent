from __future__ import annotations

import unittest

from backend.agent import route_question_to_tool_names


class AgentRoutingTests(unittest.TestCase):
    def test_routes_flight_booking_questions_to_sql(self) -> None:
        questions = [
            "Show me upcoming flights from JFK",
            "Which passengers have confirmed bookings?",
            "How many delayed flights are there?",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(route_question_to_tool_names(question), ["sql_query"])

    def test_routes_ticket_review_and_activity_questions_to_mongo(self) -> None:
        questions = [
            "Show high priority support tickets",
            "Find flight reviews with low food ratings",
            "Show mobile user activity logs for SN-10001",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(route_question_to_tool_names(question), ["mongo_query"])

    def test_routes_policy_questions_to_handbook(self) -> None:
        questions = [
            "What is the baggage policy?",
            "Explain the refund rules",
            "What are the boarding procedures?",
        ]

        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(route_question_to_tool_names(question), ["handbook_search"])

    def test_routes_multi_source_questions_to_each_relevant_tool(self) -> None:
        self.assertEqual(
            route_question_to_tool_names(
                "Show high priority support tickets and explain the refund policy"
            ),
            ["mongo_query", "handbook_search"],
        )


if __name__ == "__main__":
    unittest.main()
