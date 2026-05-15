from __future__ import annotations
from pymongo import MongoClient

from config import settings

_client: MongoClient | None = None


def get_db():
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri)
    return _client["skynova"]
