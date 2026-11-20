from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core import executor
from app.core.connector import connector
from app.models import AppUser
from app.routers.deps import current_user, get_db
from app.schemas.monitoring import SourceCreate, SourceOut, SourceTest, SourceUpdate
from app.schemas.query import BuildRequest, PreviewRequest
from app.services import query_service, source_service

router = APIRouter(tags=["sources"])


@router.get("/projects/{project_id}/sources", response_model=list[SourceOut])
def sources(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return source_service.list_sources(session, user, project_id)


@router.get("/projects/{project_id}/source-names")
def source_names(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return source_service.list_source_names(session, user, project_id)


@router.post("/projects/{project_id}/sources", response_model=SourceOut, status_code=201)
def create_source(project_id: int, data: SourceCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return source_service.create_source(session, user, project_id, data)


@router.post("/projects/{project_id}/sources/test")
async def test_source(project_id: int, data: SourceTest, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    cfg = source_service.test_config(session, user, project_id, data)
    elapsed = await executor.run(connector.test, cfg)
    return {"ok": True, "elapsed_ms": elapsed}


@router.get("/sources/{source_id}", response_model=SourceOut)
def source(source_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return source_service.out(source_service.get_source(session, user, source_id))


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: int, data: SourceUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return source_service.update_source(session, user, source_id, data)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    source_service.delete_source(session, user, source_id)
    return Response(status_code=204)


@router.get("/sources/{source_id}/schema")
async def source_schema(
    source_id: int, refresh: bool = False, user: AppUser = Depends(current_user), session: Session = Depends(get_db)
):
    return await executor.run(source_service.schema, session, user, source_id, refresh)


@router.post("/query/build")
async def build(data: BuildRequest, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    sql = await executor.run(source_service.build_query, session, user, data.source_id, data.query_model)
    return {"sql": sql}


@router.post("/query/preview")
async def preview(data: PreviewRequest, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return await query_service.preview(session, user, data)
