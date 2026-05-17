"""MongoDB tool: generates a query filter from natural language and runs it against
whitelisted SkyNova collections."""
from __future__ import annotations
import json
import logging

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pymongo.errors import PyMongoError

from backend.db.mongo import get_db
from config import settings

ALLOWED_COLLECTIONS = {"support_tickets", "flight_reviews", "user_activity_logs"}
logger = logging.getLogger(__name__)

SCHEMA_CONTEXT = """
You are a MongoDB expert for SkyNova Airlines.

COLLECTIONS:

support_tickets documents:
  ticket_id      string  -- e.g. "TKT-001"
  customer_id    string  -- frequent flyer number e.g. "SN-10001"
  customer_name  string
  flight_number  string
  subject        string
  description    string
  status         string  -- "open", "in_progress", "resolved"
  priority       string  -- "low", "medium", "high"
  created_at     ISODate
  tags           array of strings

flight_reviews documents:
  review_id      string
  customer_id    string
  customer_name  string
  flight_number  string
  route          string  -- e.g. "JFK → LAX"
  travel_date    ISODate
  cabin_class    string
  overall_rating int     -- 1 to 5
  ratings        object  -- {seat_comfort, food_quality, crew_service, punctuality, entertainment}
  review_text    string
  would_recommend bool
  submitted_at   ISODate

user_activity_logs documents:
  log_id       string
  customer_id  string
  action       string  -- e.g. "booking_created","check_in","support_ticket_opened"
  details      object
  timestamp    ISODate
  device       string  -- "web" or "mobile"

RULES:
  - Return a JSON object with keys: "collection" and "filter".
  - "collection" must be one of: support_tickets, flight_reviews, user_activity_logs.
  - "filter" must be a valid MongoDB query filter dict (use {} to return all).
  - Use regex patterns for partial string matches: {"field": {"$regex": "...", "$options": "i"}}.
  - Do NOT include projection or sort — only the filter.
  - Return ONLY the raw JSON object, no explanation, no markdown.
"""


# Operators that allow arbitrary JavaScript execution — must never appear in a filter
DANGEROUS_OPERATORS = {"$where", "$function", "$accumulator", "$expr"}


def _validate_filter(filter_obj: dict, path: str = "filter") -> None:
    """Recursively walk the filter and raise if any dangerous operator is found."""
    if not isinstance(filter_obj, dict):
        return
    for key, value in filter_obj.items():
        if key in DANGEROUS_OPERATORS:
            raise ValueError(f"Dangerous MongoDB operator '{key}' is not allowed.")
        if key.startswith("$") and key not in {
            "$and", "$or", "$nor", "$not",
            "$eq", "$ne", "$gt", "$gte", "$lt", "$lte",
            "$in", "$nin", "$exists", "$type",
            "$regex", "$options", "$elemMatch", "$size", "$all",
        }:
            raise ValueError(f"Unrecognised operator '{key}' at {path} — rejected for safety.")
        if isinstance(value, dict):
            _validate_filter(value, path=f"{path}.{key}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _validate_filter(item, path=f"{path}.{key}[]")


def _generate_mongo_query(question: str) -> dict:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0,
    )
    messages = [
        {"role": "system", "content": SCHEMA_CONTEXT},
        {
            "role": "user",
            "content": f"Generate a MongoDB query for this question:\n{question}",
        },
    ]
    response = llm.invoke(messages)
    raw = response.content.strip().strip("```json").strip("```").strip()
    return json.loads(raw)


@tool
def mongo_query(question: str) -> str:
    """Use this tool to answer questions about support tickets, flight reviews,
    and user activity logs stored in MongoDB. Input should be a natural language question."""
    query_obj = _generate_mongo_query(question)

    collection_name = query_obj.get("collection", "")
    if collection_name not in ALLOWED_COLLECTIONS:
        return json.dumps({"error": f"Collection '{collection_name}' is not allowed."})

    mongo_filter = query_obj.get("filter", {})
    if not isinstance(mongo_filter, dict):
        return json.dumps({"error": "Filter must be a JSON object."})

    try:
        _validate_filter(mongo_filter)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        db = get_db()
        docs = list(db[collection_name].find(mongo_filter, {"_id": 0}).limit(20))
    except PyMongoError:
        logger.exception("mongodb query failed")
        return json.dumps(
            {
                "error": "MongoDB is currently unavailable. Please try again later.",
                "details": "Database connection failed.",
            }
        )

    return json.dumps(
        {
            "collection": collection_name,
            "filter_used": mongo_filter,
            "count": len(docs),
            "data": docs,
        },
        default=str,
    )
