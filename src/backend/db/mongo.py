from __future__ import annotations
import os
from pymongo import MongoClient

_client: MongoClient | None = None


def get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_URI"])
    return _client["skynova"]
