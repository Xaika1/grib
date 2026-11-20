from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.query import QueryModel

SourceType = Literal["postgresql", "mysql", "sqlite"]
PanelType = Literal["line", "bar", "gauge", "stat", "table"]
PanelMode = Literal["live", "collector"]
Operator = Literal[">", ">=", "<", "<=", "==", "!="]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: SourceType
    host: str = Field(default="", max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str = Field(default="", max_length=500)
    username: str = Field(default="", max_length=100)


class SourceCreate(SourceBase):
    password: str = Field(default="", max_length=500)


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: SourceType | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = Field(default=None, max_length=500)
    username: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=500)


class SourceTest(SourceCreate):
    name: str = "test"
    source_id: int | None = None


class SourceOut(ORM, SourceBase):
    id: int
    project_id: int
    has_password: bool = False
    created_at: datetime


class PanelBase(BaseModel):
    title: str = Field(default="", max_length=200)
    type: PanelType = "line"
    mode: PanelMode = "live"
    source_id: int | None = None
    collector_id: int | None = None
    query: str = Field(default="", max_length=50_000)
    query_model: QueryModel | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    grid_w: int = Field(default=6, ge=1, le=12)
    grid_h: int = Field(default=1, ge=1, le=4)
    position: int | None = None


class PanelCreate(PanelBase):
    pass


class PanelUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    type: PanelType | None = None
    mode: PanelMode | None = None
    source_id: int | None = None
    collector_id: int | None = None
    query: str | None = Field(default=None, max_length=50_000)
    query_model: QueryModel | None = None
    clear_query_model: bool = False
    settings: dict[str, Any] | None = None
    grid_w: int | None = Field(default=None, ge=1, le=12)
    grid_h: int | None = Field(default=None, ge=1, le=4)
    position: int | None = None


class PanelOut(ORM):
    id: int
    dashboard_id: int
    title: str
    type: str
    mode: str
    source_id: int | None
    collector_id: int | None
    query: str
    settings: dict[str, Any]
    grid_w: int
    grid_h: int
    position: int


class DashboardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    default_range: str = Field(default="6h", pattern=r"^\d+[smhdw]$")
    refresh_sec: int = Field(default=30, ge=0, le=86400)


class DashboardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    default_range: str | None = Field(default=None, pattern=r"^\d+[smhdw]$")
    refresh_sec: int | None = Field(default=None, ge=0, le=86400)


class DashboardOut(ORM):
    id: int
    project_id: int
    title: str
    description: str
    default_range: str
    refresh_sec: int
    created_at: datetime
    updated_at: datetime


class DashboardFull(DashboardOut):
    panels: list[PanelOut]


class PanelOrder(BaseModel):
    panel_ids: list[int]


class DashboardImport(BaseModel):
    data: dict[str, Any]
    source_map: dict[str, int] = Field(default_factory=dict)
    collector_map: dict[str, int] = Field(default_factory=dict)
    title: str | None = None


class CollectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source_id: int
    query: str = Field(default="", max_length=50_000)
    query_model: QueryModel | None = None
    interval_sec: int = Field(default=60, ge=1, le=86400)
    enabled: bool = True


class CollectorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    source_id: int | None = None
    query: str | None = Field(default=None, max_length=50_000)
    query_model: QueryModel | None = None
    clear_query_model: bool = False
    interval_sec: int | None = Field(default=None, ge=1, le=86400)
    enabled: bool | None = None


class CollectorOut(ORM):
    id: int
    project_id: int
    source_id: int
    name: str
    query: str
    query_model: dict | None
    interval_sec: int
    enabled: bool
    last_run_at: datetime | None
    last_error: str | None
    created_at: datetime


class AlertRuleCreate(BaseModel):
    collector_id: int
    name: str = Field(min_length=1, max_length=200)
    series: str | None = Field(default=None, max_length=200)
    operator: Operator = ">"
    threshold: float
    for_sec: int = Field(default=0, ge=0, le=7 * 86400)
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    series: str | None = Field(default=None, max_length=200)
    operator: Operator | None = None
    threshold: float | None = None
    for_sec: int | None = Field(default=None, ge=0, le=7 * 86400)
    enabled: bool | None = None


class AlertRuleOut(ORM):
    id: int
    collector_id: int
    name: str
    series: str | None
    operator: str
    threshold: float
    for_sec: int
    enabled: bool
    state: str
    pending_since: datetime | None
    last_value: float | None
    last_eval_at: datetime | None


class AlertEventOut(BaseModel):
    id: int
    rule_id: int
    rule_name: str
    project_id: int
    started_at: datetime
    ended_at: datetime | None
    value: float
    message: str
