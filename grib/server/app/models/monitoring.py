from datetime import datetime

from sqlalchemy import JSON, BigInteger, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from app.db import Base


class DataSource(Base):
    __tablename__ = "data_source"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    host: Mapped[str] = mapped_column(String(255), default="")
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database: Mapped[str] = mapped_column(String(500), default="")
    username: Mapped[str] = mapped_column(String(100), default="")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Dashboard(Base):
    __tablename__ = "dashboard"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    default_range: Mapped[str] = mapped_column(String(20), default="6h")
    refresh_sec: Mapped[int] = mapped_column(default=30)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    panels: Mapped[list["Panel"]] = relationship(
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="Panel.position",
        lazy="selectin",
    )


class Collector(Base):
    __tablename__ = "collector"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    query: Mapped[str] = mapped_column(Text)
    query_model: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    interval_sec: Mapped[int] = mapped_column(default=60)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    source: Mapped[DataSource] = relationship(lazy="joined")


class Panel(Base):
    __tablename__ = "panel"

    id: Mapped[int] = mapped_column(primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(ForeignKey("dashboard.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    type: Mapped[str] = mapped_column(String(20), default="line")
    mode: Mapped[str] = mapped_column(String(20), default="live")
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_source.id", ondelete="SET NULL"), nullable=True
    )
    collector_id: Mapped[int | None] = mapped_column(
        ForeignKey("collector.id", ondelete="SET NULL"), nullable=True
    )
    query: Mapped[str] = mapped_column(Text, default="")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    grid_w: Mapped[int] = mapped_column(default=6)
    grid_h: Mapped[int] = mapped_column(default=1)
    position: Mapped[int] = mapped_column(default=0)

    dashboard: Mapped[Dashboard] = relationship(back_populates="panels")
    source: Mapped[DataSource | None] = relationship(lazy="joined")
    collector: Mapped[Collector | None] = relationship(lazy="joined")


class Sample(Base):
    __tablename__ = "sample"
    __table_args__ = (Index("ix_sample_collector_ts", "collector_id", "ts"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collector.id", ondelete="CASCADE"))
    ts: Mapped[datetime]
    series: Mapped[str] = mapped_column(String(200))
    value: Mapped[float] = mapped_column(Float)


class AlertRule(Base):
    __tablename__ = "alert_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collector.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    series: Mapped[str | None] = mapped_column(String(200), nullable=True)
    operator: Mapped[str] = mapped_column(String(4), default=">")
    threshold: Mapped[float] = mapped_column(Float)
    for_sec: Mapped[int] = mapped_column(default=0)
    enabled: Mapped[bool] = mapped_column(default=True)
    state: Mapped[str] = mapped_column(String(10), default="ok")
    pending_since: Mapped[datetime | None] = mapped_column(nullable=True)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_eval_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    collector: Mapped[Collector] = relationship(lazy="joined")


class AlertEvent(Base):
    __tablename__ = "alert_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rule.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    value: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(String(500), default="")

    rule: Mapped[AlertRule] = relationship(lazy="joined")
