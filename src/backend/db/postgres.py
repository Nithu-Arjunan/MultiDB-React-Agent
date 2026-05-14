from __future__ import annotations
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    return psycopg2.connect(os.environ["SUPABASE_URI"], cursor_factory=RealDictCursor)
