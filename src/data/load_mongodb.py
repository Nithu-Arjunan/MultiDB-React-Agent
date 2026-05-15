"""Load data/mongodb_seed.json into a local or Atlas MongoDB instance.

Run once:
    uv add pymongo                 (or: pip install pymongo)
    export MONGODB_URI="mongodb://localhost:27017"   # or your Atlas SRV URI
    uv run python data/load_mongodb.py

Behaviour:
- Drops and recreates the three SkyNova collections in database `skynova`.
- Converts ISO-8601 datetime strings to BSON Date so range queries work.
"""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path

from pymongo import MongoClient

from config import settings

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?$")


def _coerce_dates(obj):
    """Recursively walk and turn ISO-8601 strings into datetime objects."""
    if isinstance(obj, dict):
        return {k: _coerce_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_dates(v) for v in obj]
    if isinstance(obj, str) and ISO_RE.match(obj):
        return datetime.fromisoformat(obj.replace(" ", "T").rstrip("Z"))
    return obj


def main() -> None:
    seed_path = Path(__file__).parent / "mongodb_seed.json"
    raw = json.loads(seed_path.read_text(encoding="utf-8"))

    uri = settings.mongo_uri
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client["skynova"]

    for coll_name in ("support_tickets", "flight_reviews", "user_activity_logs"):
        docs = _coerce_dates(raw[coll_name])
        db[coll_name].drop()
        if docs:
            db[coll_name].insert_many(docs)
        print(f"  {coll_name}: inserted {len(docs)} docs")

    db["support_tickets"].create_index("customer_id")
    db["support_tickets"].create_index("status")
    db["flight_reviews"].create_index("customer_id")
    db["flight_reviews"].create_index("flight_number")
    db["user_activity_logs"].create_index("customer_id")
    db["user_activity_logs"].create_index([("timestamp", -1)])

    print(f"Loaded into {uri} -> db 'skynova'.")


if __name__ == "__main__":
    main()
