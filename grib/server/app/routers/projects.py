from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.models import AppUser
from app.routers.deps import current_user, get_db
from app.schemas.auth import MemberCreate, MemberOut, MemberUpdate, ProjectCreate, ProjectOut, ProjectUpdate
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def projects(user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return project_service.list_projects(session, user)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return project_service.create_project(session, user, data)


@router.get("/{project_id}", response_model=ProjectOut)
def project(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return project_service.get_project(session, user, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, data: ProjectUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return project_service.update_project(session, user, project_id, data)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    project_service.delete_project(session, user, project_id)
    return Response(status_code=204)


@router.get("/{project_id}/members", response_model=list[MemberOut])
def members(project_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return project_service.list_members(session, user, project_id)


@router.post("/{project_id}/members", response_model=MemberOut, status_code=201)
def add_member(project_id: int, data: MemberCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return project_service.add_member(session, user, project_id, data)


@router.patch("/{project_id}/members/{member_id}", response_model=MemberOut)
def update_member(
    project_id: int, member_id: int, data: MemberUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)
):
    return project_service.update_member(session, user, project_id, member_id, data)


@router.delete("/{project_id}/members/{member_id}", status_code=204)
def remove_member(project_id: int, member_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    project_service.remove_member(session, user, project_id, member_id)
    return Response(status_code=204)
