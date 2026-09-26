import sqlite3

from contextlib import contextmanager
from pathlib import Path

from app.core.config import BASE_DIR


DEFAULT_DATABASE_PATH = (
    BASE_DIR
    / "data"
    / "mizan.db"
)


class Database:
    def __init__(
        self,
        path: Path | str | None = None,
    ):
        self.path = Path(
            path or DEFAULT_DATABASE_PATH
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=30,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA foreign_keys = ON;"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL;"
        )

        connection.execute(
            "PRAGMA busy_timeout = 5000;"
        )

        return connection

    @contextmanager
    def session(self):
        connection = self.connect()

        try:
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()


_default_database: Database | None = None


def get_default_database() -> Database:
    global _default_database

    if _default_database is None:
        _default_database = Database()

    return _default_database