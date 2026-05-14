"""Run this once to verify both MongoDB and Supabase connections are working.

    uv run python src/data/verify_connections.py
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parents[1] / ".env")


def check_mongodb() -> None:
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError

    uri = os.environ["MONGO_URI"]
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        info = client.server_info()
        print(f"[OK] MongoDB connected — version {info['version']}")
    except ServerSelectionTimeoutError as e:
        print(f"[FAIL] MongoDB: {e}")
    finally:
        client.close()


def check_supabase() -> None:
    import psycopg2

    uri = os.environ["SUPABASE_URI"]
    try:
        conn = psycopg2.connect(uri, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM passengers;")
        count = cur.fetchone()[0]
        print(f"[OK] Supabase connected — passengers table has {count} row(s)")
        conn.close()
    except Exception as e:
        print(f"[FAIL] Supabase: {e}")


if __name__ == "__main__":
    print("Checking connections...\n")
    check_mongodb()
    check_supabase()
