from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import crypto
from app.core.connector import SourceConfig, connector, resolve_sqlite_path
from app.core.errors import BadRequest, Conflict
from app.core.permissions import ensure
from app.core.query_builder import build_sql
from app.core.schema_inspector import SchemaInspector
from app.models import AppUser, DataSource
from app.repositories import ProjectRepo, SourceRepo
from app.schemas.monitoring import SourceCreate, SourceOut, SourceTest, SourceUpdate
from app.schemas.query import QueryModel

inspector = SchemaInspector(connector)


def config_of(src: DataSource) -> SourceConfig:
    return SourceConfig(
        id=src.id,
        type=src.type,
        host=src.host,
        port=src.port,
        database=src.database,
        username=src.username,
        password=crypto.decrypt(src.password_enc),
    )


def out(src: DataSource) -> SourceOut:
    return SourceOut(
        id=src.id,
        project_id=src.project_id,
        name=src.name,
        type=src.type,
        host=src.host,
        port=src.port,
        database=src.database,
        username=src.username,
        has_password=bool(src.password_enc),
        created_at=src.created_at,
    )


def _validate(type_: str, host: str, database: str) -> None:
    if type_ == "sqlite":
        if not database:
            raise BadRequest("Для SQLite укажите имя файла базы данных")
        resolve_sqlite_path(database)
    elif not host:
        raise BadRequest("Укажите адрес сервера базы данных")


def get_source(session: Session, user: AppUser, source_id: int, permission: str = "source.view") -> DataSource:
    src = SourceRepo(session).get_or_404(source_id)
    ensure(session, user, src.project_id, permission)
    return src


def list_sources(session: Session, user: AppUser, project_id: int) -> list[SourceOut]:
    ensure(session, user, project_id, "source.view")
    return [out(s) for s in SourceRepo(session).for_project(project_id)]


def list_source_names(session: Session, user: AppUser, project_id: int) -> list[dict]:
    ensure(session, user, project_id, "query.run")
    return [{"id": s.id, "name": s.name, "type": s.type} for s in SourceRepo(session).for_project(project_id)]


def create_source(session: Session, user: AppUser, project_id: int, data: SourceCreate) -> SourceOut:
    ensure(session, user, project_id, "source.manage")
    ProjectRepo(session).get_or_404(project_id)
    repo = SourceRepo(session)
    if repo.by_name(project_id, data.name):
        raise Conflict(f"Источник «{data.name}» уже есть в проекте")
    _validate(data.type, data.host, data.database)
    src = repo.add(
        DataSource(
            project_id=project_id,
            name=data.name,
            type=data.type,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password_enc=crypto.encrypt(data.password),
        )
    )
    session.commit()
    return out(src)


def update_source(session: Session, user: AppUser, source_id: int, data: SourceUpdate) -> SourceOut:
    src = get_source(session, user, source_id, "source.manage")
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] != src.name:
        if SourceRepo(session).by_name(src.project_id, fields["name"]):
            raise Conflict(f"Источник «{fields['name']}» уже есть в проекте")
    for key in ("name", "type", "host", "port", "database", "username"):
        if key in fields and (fields[key] is not None or key == "port"):
            setattr(src, key, fields[key])
    if fields.get("password") is not None:
        src.password_enc = crypto.encrypt(fields["password"])
    _validate(src.type, src.host, src.database)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Источник с таким именем уже есть") from exc
    connector.invalidate(src.id)
    inspector.invalidate()
    return out(src)


def delete_source(session: Session, user: AppUser, source_id: int) -> None:
    src = get_source(session, user, source_id, "source.manage")
    SourceRepo(session).delete(src)
    session.commit()
    connector.invalidate(source_id)


def test_config(session: Session, user: AppUser, project_id: int, data: SourceTest) -> SourceConfig:
    ensure(session, user, project_id, "source.manage")
    password = data.password
    if data.source_id and not password:
        src = get_source(session, user, data.source_id, "source.manage")
        password = crypto.decrypt(src.password_enc)
    _validate(data.type, data.host, data.database)
    return SourceConfig(
        type=data.type, host=data.host, port=data.port, database=data.database, username=data.username, password=password
    )


def schema(session: Session, user: AppUser, source_id: int, refresh: bool = False) -> dict:
    src = get_source(session, user, source_id, "query.run")
    return inspector.schema(config_of(src), refresh=refresh)


def build_query(session: Session, user: AppUser, source_id: int, model: QueryModel) -> str:
    src = get_source(session, user, source_id, "query.run")
    cfg = config_of(src)
    table = inspector.table(cfg, model.table)
    return build_sql(model, table, connector.engine(cfg).dialect)


def build_for_source(src: DataSource, model: QueryModel) -> str:
    cfg = config_of(src)
    return build_sql(model, inspector.table(cfg, model.table), connector.engine(cfg).dialect)
