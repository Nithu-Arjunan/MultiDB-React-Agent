"""Chunk the SkyNova handbook, embed with OpenAI, and load into Supabase pgvector.

Run once:
    uv run python src/data/load_handbook.py

Requires OPENAI_API_KEY and SUPABASE_URI in src/.env
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parents[1] / ".env")

HANDBOOK_PATH = Path(__file__).parent / "skynova_handbook.txt"
CHUNK_SIZE = 400      # target words per chunk
CHUNK_OVERLAP = 50    # words of overlap between chunks
EMBED_MODEL = "text-embedding-3-small"  # 1536 dimensions


def split_into_chunks(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return chunks


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def main() -> None:
    handbook_text = HANDBOOK_PATH.read_text(encoding="utf-8")

    # Split by section headers first, then chunk each section
    sections = re.split(r"\n(?=#{1,3} )", handbook_text)
    all_chunks: list[tuple[str, int, str]] = []  # (source, index, content)

    for section in sections:
        header_match = re.match(r"#{1,3} (.+)", section)
        source = header_match.group(1).strip() if header_match else "General"
        chunks = split_into_chunks(section, CHUNK_SIZE, CHUNK_OVERLAP)
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                all_chunks.append((source, i, chunk.strip()))

    print(f"Created {len(all_chunks)} chunks from handbook")

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    texts = [c[2] for c in all_chunks]

    print("Embedding chunks via OpenAI...")
    embeddings = embed_texts(openai_client, texts)
    print(f"Got {len(embeddings)} embeddings")

    conn = psycopg2.connect(os.environ["SUPABASE_URI"])
    cur = conn.cursor()

    cur.execute("TRUNCATE TABLE handbook_chunks RESTART IDENTITY;")

    for (source, idx, content), embedding in zip(all_chunks, embeddings):
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        cur.execute(
            "INSERT INTO handbook_chunks (source, chunk_index, content, embedding) VALUES (%s, %s, %s, %s::vector)",
            (source, idx, content, vec_str),
        )

    conn.commit()
    cur.close()
    conn.close()

    print(f"Loaded {len(all_chunks)} chunks into Supabase handbook_chunks table.")


if __name__ == "__main__":
    main()
