"""Small PostgreSQL connection adapter used by the local API and Lambda."""

from __future__ import annotations

import os
import re
from typing import Any


class PostgresConnection:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    @classmethod
    def from_environment(cls) -> "PostgresConnection":
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError(
                f"PostgreSQL driver import failed: {error}"
            ) from error
        from psycopg.rows import dict_row

        connection = psycopg.connect(
            host=os.environ["DB_HOST"],
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "postgres"),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            sslmode=os.getenv("DB_SSLMODE", "require"),
            row_factory=dict_row,
        )
        return cls(connection)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        sql = sql.replace("?", "%s")
        if "INSERT OR IGNORE" in sql.upper():
            sql = re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", sql, flags=re.IGNORECASE)
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        return self._connection.execute(sql, params)

    @property
    def closed(self) -> bool:
        return bool(self._connection.closed)

    def executescript(self, sql: str) -> None:
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "PostgresConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exception_type: Any, exception: Any, traceback: Any) -> None:
        self._connection.__exit__(exception_type, exception, traceback)
