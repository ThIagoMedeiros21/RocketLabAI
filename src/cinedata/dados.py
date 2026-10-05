"""Acesso ao SQLite: somente leitura, limites e esquema real."""

import sqlite3
import time
from contextlib import closing
from pathlib import Path

TABLES = set(
    [
        "dim_movies",
        "fact_movies_performance",
        "dim_genres",
        "dim_people",
        "dim_companies",
        "dim_reviews",
        "movie_reviews",
        "bridge_movie_genre",
        "bridge_movie_person",
        "bridge_movie_company",
    ]
)


def connect(path, snapshot=False):
    p = Path(path).expanduser().resolve(strict=True)
    # immutable é opt-in: somente para arquivo estático, sem escritor nem WAL pendente.
    c = sqlite3.connect(p.as_uri() + "?mode=ro" + ("&immutable=1" if snapshot else ""), uri=True)
    c.execute("PRAGMA query_only=ON")
    return c


def schema(c):
    return "\n".join(
        sql
        for name, sql in c.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
        if name in TABLES and sql
    )


def execute(c, sql, timeout=10, limit=100, parameters=None):
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("Consulta vazia.")

    def authorize(action, a, b, db, source):
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and a in TABLES:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and (b or "").lower() in {
            "abs",
            "avg",
            "count",
            "sum",
            "min",
            "max",
            "total",
            "round",
            "coalesce",
            "nullif",
            "date",
            "datetime",
            "strftime",
            "julianday",
            "lower",
            "upper",
            "like",
            "substr",
            "length",
            "trim",
            "replace",
            "ifnull",
            "row_number",
            "rank",
            "dense_rank",
        }:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    deadline = time.monotonic() + timeout
    c.set_authorizer(authorize)
    c.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        cur = c.execute(sql, parameters or {})
        if cur.description is None:
            raise ValueError("A consulta não retornou colunas.")
        rows = cur.fetchmany(limit + 1)
        return {
            "colunas": [x[0] for x in cur.description],
            "linhas": rows[:limit],
            "truncado": len(rows) > limit,
        }
    finally:
        c.set_authorizer(None)
        c.set_progress_handler(None, 0)


def get_schema(db_path, snapshot=False):
    with closing(connect(db_path, snapshot)) as conn:
        return schema(conn)


def execute_sql(db_path, sql, snapshot=False, parameters=None):
    with closing(connect(db_path, snapshot)) as conn:
        return execute(conn, sql, parameters=parameters)


def get_table_info(db_path, table, snapshot=False):
    if table not in TABLES:
        raise ValueError("Tabela não permitida.")
    with closing(connect(db_path, snapshot)) as conn:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if row is None:
            raise ValueError("Tabela não existe neste banco.")
        return {"ddl": row[0], "amostra": execute(conn, f'SELECT * FROM "{table}" LIMIT 2')}


def get_distinct_values(db_path, table, column, snapshot=False):
    if table not in TABLES:
        raise ValueError("Tabela não permitida.")
    with closing(connect(db_path, snapshot)) as conn:
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if column not in columns:
            raise ValueError("Coluna não existe nesta tabela.")
        quoted = column.replace('"', '""')
        return execute(conn, f'SELECT DISTINCT "{quoted}" FROM "{table}" LIMIT 20')
