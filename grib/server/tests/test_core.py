from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table
from sqlalchemy.dialects import mysql, postgresql, sqlite

from app.core import query_guard, time_macros
from app.core.errors import BadRequest, QueryError
from app.core.normalizer import normalize
from app.core.query_builder import build_sql
from app.schemas.query import QueryModel


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from orders;",
        'SELECT "Region", `amount` FROM orders',
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SELECT 'drop table x; delete' AS s",
        "SELECT created_at::date FROM orders -- комментарий; drop",
    ],
)
def test_guard_allows(sql):
    assert query_guard.check(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "DELETE FROM orders",
        "SELECT 1; DROP TABLE orders",
        "UPDATE orders SET amount = 0",
        "SELECT * INTO backup FROM orders",
        "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d",
        "SELECT pg_sleep(100)",
        "PRAGMA table_info(orders)",
        "SELECT pg_read_file('/etc/passwd')",
        'SELECT "pg_read_file"(\'/etc/passwd\')',
        "SELECT pg_catalog.pg_terminate_backend(1)",
        "SELECT set_config('default_transaction_read_only', 'off', false)",
        "SELECT query_to_xml('select 1', true, true, '')",
        "SELECT lo_import('/etc/passwd')",
    ],
)
def test_guard_rejects(sql):
    with pytest.raises(QueryError):
        query_guard.check(sql)


def test_time_macros():
    sql = time_macros.apply(
        "SELECT * FROM t WHERE ts >= $from AND ts < ${to} -- $interval",
        datetime(2026, 1, 1, 10, 0, 0),
        datetime(2026, 1, 1, 12, 0, 0),
    )
    assert "'2026-01-01 10:00:00'" in sql and "'2026-01-01 12:00:00'" in sql
    assert "-- 36" in sql


def test_normalize_time_series_with_labels():
    rows = [
        ("2026-01-01 10:00:00", "Москва", 3),
        ("2026-01-01 10:00:00", "Казань", 1),
        ("2026-01-01 11:00:00", "Москва", Decimal("5.5")),
    ]
    out = normalize(["time", "region", "orders"], rows)
    assert out.time_column == "time"
    names = {s["name"]: s["points"] for s in out.series}
    assert set(names) == {"Москва", "Казань"}
    assert names["Москва"][1][1] == 5.5
    assert names["Москва"][0][0] < names["Москва"][1][0]


def test_normalize_snapshot():
    out = normalize(["name", "size"], [("orders", 5), ("emails", 50)])
    assert out.time_column is None
    assert [s["name"] for s in out.series] == ["orders", "emails"]
    assert out.table["rows"] == [["orders", 5], ["emails", 50]]


def test_normalize_multiple_numeric():
    out = normalize(["ts", "a", "b"], [(datetime(2026, 1, 1), 1, 2)])
    assert [s["name"] for s in out.series] == ["a", "b"]


_TABLE = Table(
    "orders",
    MetaData(),
    Column("id", Integer),
    Column("created_at", DateTime),
    Column("amount", Numeric),
    Column("region", String),
    Column("status", String),
)

_MODEL = QueryModel.model_validate(
    {
        "table": "orders",
        "time": {"column": "created_at", "bucket": "hour"},
        "select": [{"column": "amount", "agg": "sum", "alias": "revenue"}],
        "where": [{"column": "status", "op": "=", "value": "paid'; drop table x; --"}],
        "group_by": ["region"],
    }
)


@pytest.mark.parametrize(
    "dialect,fragment",
    [
        (postgresql.dialect(), "date_trunc('hour', orders.created_at)"),
        (mysql.dialect(), "date_format(orders.created_at, '%Y-%m-%d %H:00:00')"),
        (sqlite.dialect(), "strftime('%Y-%m-%d %H:00:00', orders.created_at)"),
    ],
)
def test_builder_dialects(dialect, fragment):
    sql = build_sql(_MODEL, _TABLE, dialect)
    assert fragment in sql
    assert "$from" in sql and "$to" in sql
    assert "GROUP BY" in sql
    assert "'paid''; drop table x; --'" in sql or "'paid\\'; drop table x; --'" in sql
    query_guard.check(time_macros.apply(sql, datetime(2026, 1, 1), datetime(2026, 1, 2)))


def test_builder_rejects_unknown_column():
    model = QueryModel.model_validate({"table": "orders", "select": [{"column": "password"}]})
    with pytest.raises(BadRequest):
        build_sql(model, _TABLE, sqlite.dialect())


def test_builder_count_star_and_in():
    model = QueryModel.model_validate(
        {
            "table": "orders",
            "select": [{"column": "*", "agg": "count"}],
            "where": [{"column": "region", "op": "in", "value": "Москва, Казань"}],
            "group_by": ["status"],
            "order_by": [{"column": "count", "dir": "desc"}],
            "limit": 5,
        }
    )
    sql = build_sql(model, _TABLE, sqlite.dialect())
    assert "count(*) AS count" in sql
    assert "IN ('Москва', 'Казань')" in sql
    assert "ORDER BY count DESC" in sql
    assert "LIMIT 5" in sql


def test_guard_hash_is_not_a_comment():
    with pytest.raises(QueryError):
        query_guard.check("SELECT 1 # 2; DROP TABLE orders")
