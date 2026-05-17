"""SQL tool: generates a safe SELECT query from natural language, validates it, then runs it."""
from __future__ import annotations
import json
import logging
import re

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import psycopg2

from backend.db.postgres import get_connection
from config import settings

# ── Schema + business rules injected into every SQL generation call ──────────
SCHEMA_CONTEXT = """
You are a SQL expert for SkyNova Airlines (PostgreSQL / Supabase).

SCHEMA:
Table: passengers
  id           SERIAL PRIMARY KEY
  name         TEXT
  email        TEXT UNIQUE
  tier         TEXT  -- values: 'bronze','silver','gold','platinum'
  ff_number    TEXT  -- frequent flyer number e.g. 'SN-10001'

Table: flights
  id             SERIAL PRIMARY KEY
  flight_number  TEXT   -- e.g. 'SN101'
  origin         TEXT   -- IATA code e.g. 'JFK'
  destination    TEXT   -- IATA code e.g. 'LAX'
  departure_time TIMESTAMPTZ
  arrival_time   TIMESTAMPTZ
  status         TEXT   -- 'scheduled','delayed','cancelled','completed'
  aircraft_type  TEXT
  base_price     NUMERIC(10,2)

Table: bookings
  id           SERIAL PRIMARY KEY
  passenger_id INT  -- FK → passengers.id
  flight_id    INT  -- FK → flights.id
  seat_number  TEXT
  booking_date TIMESTAMPTZ
  status       TEXT   -- 'confirmed','cancelled','checked_in'
  cabin_class  TEXT   -- 'economy','business','first'

RELATIONSHIPS:
  bookings.passenger_id → passengers.id
  bookings.flight_id    → flights.id

BUSINESS RULES:
  - Only generate SELECT queries. Never INSERT, UPDATE, DELETE, DROP, CREATE, ALTER.
  - Always add LIMIT 20 unless the query is a COUNT or aggregation.
  - Use ILIKE for case-insensitive text matching.
  - Select only the columns needed to answer the question.
  - Do NOT expose email or internal id columns unless explicitly asked.
"""

DANGEROUS_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXECUTE|EXEC)\b",
    re.IGNORECASE,
)
DEFAULT_LIMIT = 20
STATEMENT_TIMEOUT_MS = 5000
logger = logging.getLogger(__name__)


def _generate_sql(question: str) -> str:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0,
    )
    messages = [
        {"role": "system", "content": SCHEMA_CONTEXT},
        {
            "role": "user",
            "content": (
                f"Write a PostgreSQL SELECT query to answer this question:\n{question}\n\n"
                "Return ONLY the raw SQL query with no explanation, no markdown, no code fences."
            ),
        },
    ]
    response = llm.invoke(messages)
    return response.content.strip()


def _validate_sql(sql: str) -> list[str]:
    warnings: list[str] = []
    stripped = sql.strip().lstrip(";").strip()

    if not stripped.upper().startswith("SELECT"):
        raise ValueError(f"Only SELECT queries are allowed. Got: {stripped[:60]}")

    if DANGEROUS_KEYWORDS.search(sql):
        match = DANGEROUS_KEYWORDS.search(sql)
        raise ValueError(f"Dangerous keyword detected in query: {match.group()}")

    if "LIMIT" not in sql.upper() and "COUNT" not in sql.upper():
        warnings.append("No LIMIT clause found — results may be large.")

    return warnings


def _ensure_limit(sql: str, limit: int = DEFAULT_LIMIT) -> str:
    stripped = sql.strip()
    if "LIMIT" in stripped.upper() or "COUNT" in stripped.upper():
        return sql

    semicolon = ";" if stripped.endswith(";") else ""
    without_semicolon = stripped[:-1].rstrip() if semicolon else stripped
    return f"{without_semicolon} LIMIT {limit}{semicolon}"


def _run_sql(sql: str) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT_MS}ms'")
        cur.execute(sql)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@tool
def sql_query(question: str) -> str:
    """Use this tool to answer questions about flights, passengers, and bookings
    stored in the PostgreSQL database. Input should be a natural language question."""
    sql = _generate_sql(question)
    warnings = _validate_sql(sql)
    sql = _ensure_limit(sql)

    try:
        rows = _run_sql(sql)
    except psycopg2.Error:
        logger.exception("supabase query failed")
        return json.dumps(
            {
                "error": "Supabase is currently unavailable. Please try again later.",
                "details": "Database connection failed.",
            }
        )

    result = {
        "sql_executed": sql,
        "row_count": len(rows),
        "data": rows[:20],
    }
    if warnings:
        result["warnings"] = warnings

    return json.dumps(result, default=str)
