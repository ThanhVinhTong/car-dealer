from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


class PostgresStorage:
    """Read-only access to existing PostgreSQL/Supabase reference data."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def load_makes(self) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT make_id, make_name, created_at
            FROM makes
            ORDER BY make_name
            """
        )

    def load_models(self) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT model_id, make_id, model_name, created_at
            FROM models
            ORDER BY make_id, model_id
            """
        )

    def load_reference_data(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return self.load_makes(), self.load_models()

    def _fetch_all(self, query: str) -> list[dict[str, Any]]:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2 is required for PostgreSQL access. Install requirements.txt."
            ) from exc

        connection = None
        try:
            connection = psycopg2.connect(self.database_url)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except psycopg2.OperationalError as exc:
            raise RuntimeError(_format_connection_error(self.database_url, exc)) from exc
        finally:
            if connection is not None:
                connection.close()


def _format_connection_error(database_url: str, exc: Exception) -> str:
    host = _safe_database_host(database_url)
    base_message = f"Could not connect to PostgreSQL/Supabase"
    if host:
        base_message += f" host {host!r}"

    return (
        f"{base_message}: {exc}\n"
        "Check that DATABASE_URL is copied from Supabase Dashboard > Connect, "
        "the project is active, the database password is URL-encoded if it contains "
        "special characters, and the connection string includes sslmode=require. "
        "If you are using the direct db.[project-ref].supabase.co endpoint from an "
        "IPv4-only network, use Supabase's Session pooler connection string instead "
        "or enable the IPv4 add-on."
    )


def _safe_database_host(database_url: str) -> str | None:
    try:
        parsed = urlparse(database_url)
    except Exception:
        return None
    return parsed.hostname
