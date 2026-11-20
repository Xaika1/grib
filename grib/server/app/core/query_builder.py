from sqlalchemy import Table, and_, func, literal, literal_column, or_, select
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import BadRequest
from app.schemas.query import Condition, QueryModel

_MYSQL_FMT = {"minute": "%Y-%m-%d %H:%i:00", "hour": "%Y-%m-%d %H:00:00", "day": "%Y-%m-%d"}
_SQLITE_FMT = {"minute": "%Y-%m-%d %H:%M:00", "hour": "%Y-%m-%d %H:00:00", "day": "%Y-%m-%d"}


def _bucket(col: ColumnElement, bucket: str, dialect: str) -> ColumnElement:
    if bucket == "none":
        return col
    if dialect == "postgresql":
        return func.date_trunc(literal(bucket), col)
    if dialect in ("mysql", "mariadb"):
        return func.date_format(col, literal(_MYSQL_FMT[bucket]))
    if dialect == "sqlite":
        return func.strftime(literal(_SQLITE_FMT[bucket]), col)
    raise BadRequest(f"Группировка по времени не поддерживается для {dialect}")


def _lit(value):
    if isinstance(value, (list, tuple, dict)):
        raise BadRequest("Ожидалось одно значение, а не список")
    return literal(value)


def _condition(col: ColumnElement, cond: Condition) -> ColumnElement:
    op, v = cond.op, cond.value
    if op == "is null":
        return col.is_(None)
    if op == "is not null":
        return col.is_not(None)
    if v is None:
        raise BadRequest(f"Не задано значение условия для столбца «{cond.column}»")
    if op == "in":
        values = v if isinstance(v, list) else [x.strip() for x in str(v).split(",") if x.strip()]
        if not values:
            raise BadRequest(f"Пустой список значений для «{cond.column}»")
        return col.in_([_lit(x) for x in values])
    if op == "like":
        return col.like(_lit(str(v)))
    if op == "not like":
        return col.not_like(_lit(str(v)))
    value = _lit(v)
    return {
        "=": col == value,
        "!=": col != value,
        ">": col > value,
        ">=": col >= value,
        "<": col < value,
        "<=": col <= value,
    }[op]


def build_sql(model: QueryModel, table: Table, dialect: Dialect) -> str:
    def column(name: str) -> ColumnElement:
        if name not in table.c:
            raise BadRequest(f"Столбец «{name}» не найден в таблице «{table.name}»")
        return table.c[name]

    has_agg = any(item.agg != "none" for item in model.select)
    selected: list[ColumnElement] = []
    labels: dict[str, ColumnElement] = {}
    group: list[ColumnElement] = []
    time_col = None

    if model.time:
        time_col = column(model.time.column)
        expr = _bucket(time_col, model.time.bucket, dialect.name)
        labelled = expr.label("time")
        selected.append(labelled)
        labels["time"] = labelled
        group.append(expr)

    for item in model.select:
        if item.column == "*":
            if item.agg != "count":
                raise BadRequest("«*» можно использовать только с COUNT")
            expr = func.count()
            name = item.alias or "count"
        else:
            col = column(item.column)
            expr = col if item.agg == "none" else getattr(func, item.agg)(col)
            name = item.alias or (item.column if item.agg == "none" else f"{item.agg}_{item.column}")
            if item.agg == "none":
                group.append(col)
        if name in labels:
            raise BadRequest(f"Повторяющееся имя столбца в результате: «{name}»")
        labelled = expr.label(name)
        selected.append(labelled)
        labels[name] = labelled

    for name in model.group_by:
        col = column(name)
        if name not in labels:
            labelled = col.label(name)
            selected.append(labelled)
            labels[name] = labelled
        group.append(col)

    if not selected:
        raise BadRequest("Выберите хотя бы один столбец")

    stmt = select(*selected).select_from(table)

    filters = []
    if time_col is not None and model.time and model.time.filter:
        filters.append(and_(time_col >= literal_column("$from"), time_col < literal_column("$to")))
    user = [_condition(column(c.column), c) for c in model.where]
    if user:
        filters.append(or_(*user) if model.where_mode == "or" else and_(*user))
    if filters:
        stmt = stmt.where(and_(*filters))

    if has_agg:
        unique = []
        for g in group:
            if not any(g is u for u in unique):
                unique.append(g)
        stmt = stmt.group_by(*unique)

    if model.order_by:
        for item in model.order_by:
            target = labels.get(item.column)
            expr = target if target is not None else column(item.column)
            stmt = stmt.order_by(expr.desc() if item.dir == "desc" else expr.asc())
    elif time_col is not None:
        stmt = stmt.order_by(labels["time"].asc())

    if model.limit:
        stmt = stmt.limit(model.limit)

    sql = str(stmt.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    if dialect.paramstyle in ("format", "pyformat"):
        sql = sql.replace("%%", "%")
    return sql
