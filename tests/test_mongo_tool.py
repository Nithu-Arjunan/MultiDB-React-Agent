from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from pymongo.errors import PyMongoError

from backend.tools.mongo_tool import mongo_query


class MongoToolErrorHandlingTests(unittest.TestCase):
    def test_returns_friendly_error_when_mongodb_query_fails(self) -> None:
        collection = Mock()
        collection.find.side_effect = PyMongoError(
            "SSL handshake failed: ac-qcd8tyy-shard-00-01.cxpebby.mongodb.net:27017"
        )
        db = {"support_tickets": collection}

        with (
            patch(
                "backend.tools.mongo_tool._generate_mongo_query",
                return_value={"collection": "support_tickets", "filter": {}},
            ),
            patch("backend.tools.mongo_tool.get_db", return_value=db),
            self.assertLogs("backend.tools.mongo_tool", level="ERROR") as logs,
        ):
            result = mongo_query.invoke({"question": "Show support tickets"})

        data = json.loads(result)
        self.assertEqual(data["error"], "MongoDB is currently unavailable. Please try again later.")
        self.assertEqual(data["details"], "Database connection failed.")
        self.assertNotIn("SSL handshake", result)
        self.assertNotIn("cxpebby.mongodb.net", result)
        self.assertIn("mongodb query failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
