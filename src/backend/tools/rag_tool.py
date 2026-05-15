"""RAG tool: embeds the question and searches handbook_chunks via pgvector cosine similarity."""
from __future__ import annotations
import json

from langchain_core.tools import tool
from openai import OpenAI

from backend.db.postgres import get_connection
from config import settings

EMBED_MODEL = "text-embedding-3-small"
TOP_K = 5


def _embed(text: str) -> list[float]:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=EMBED_MODEL, input=[text])
    return response.data[0].embedding


@tool
def handbook_search(question: str) -> str:
    """Use this tool to answer questions about SkyNova Airlines policies, rules,
    procedures, and guidelines from the passenger handbook. Input should be the
    question or topic to look up."""
    embedding = _embed(question)
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT source, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM handbook_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vec_str, vec_str, TOP_K),
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    return json.dumps(
        {
            "source": "SkyNova Passenger Handbook",
            "top_chunks": rows,
        },
        default=str,
    )
