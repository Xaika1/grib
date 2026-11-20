from typing import Literal

from pydantic import BaseModel, Field

Agg = Literal["none", "count", "sum", "avg", "min", "max"]
Op = Literal["=", "!=", ">", ">=", "<", "<=", "like", "not like", "in", "is null", "is not null"]
Scalar = str | int | float | bool


class SelectItem(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    agg: Agg = "none"
    alias: str | None = Field(default=None, pattern=r"^[\w ]{1,64}$")


class TimeSpec(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    bucket: Literal["none", "minute", "hour", "day"] = "hour"
    filter: bool = True


class Condition(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    op: Op = "="
    value: Scalar | list[Scalar] | None = None


class OrderItem(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    dir: Literal["asc", "desc"] = "asc"


class QueryModel(BaseModel):
    table: str = Field(min_length=1, max_length=200)
    time: TimeSpec | None = None
    select: list[SelectItem] = Field(default_factory=list)
    where: list[Condition] = Field(default_factory=list)
    where_mode: Literal["and", "or"] = "and"
    group_by: list[str] = Field(default_factory=list)
    order_by: list[OrderItem] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=100_000)


class BuildRequest(BaseModel):
    source_id: int
    query_model: QueryModel


class PreviewRequest(BaseModel):
    project_id: int
    mode: Literal["live", "collector"] = "live"
    source_id: int | None = None
    collector_id: int | None = None
    query: str = ""
    query_model: QueryModel | None = None
    from_ms: int | None = None
    to_ms: int | None = None
