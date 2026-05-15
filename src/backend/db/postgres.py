from __future__ import annotations
import psycopg2
from psycopg2.extras import RealDictCursor

from config import settings


def get_connection():
    return psycopg2.connect(settings.supabase_uri, cursor_factory=RealDictCursor)
