from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.permissions import PERMISSIONS
from app.models import AppUser
from app.routers.deps import current_user, get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeOut,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
    TokenOut,
    UserBrief,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginRequest, session: Session = Depends(get_db)):
    return auth_service.login(session, data.login, data.password)


@router.get("/auth/me", response_model=MeOut)
def me(user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.me(session, user)


@router.post("/auth/password", response_model=TokenOut)
def change_password(data: ChangePasswordRequest, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.change_password(session, user, data)


@router.get("/users", response_model=list[UserOut])
def users(q: str = "", user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.list_users(session, user, q)


@router.get("/users/directory", response_model=list[UserBrief])
def users_directory(q: str = "", _: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.directory(session, q)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.create_user(session, user, data)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.update_user(session, user, user_id, data)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    auth_service.delete_user(session, user, user_id)
    return Response(status_code=204)


@router.get("/permissions", response_model=list[PermissionOut])
def permissions(_: AppUser = Depends(current_user)):
    return [PermissionOut(code=c, description=d) for c, d in PERMISSIONS.items()]


@router.get("/roles", response_model=list[RoleOut])
def roles(_: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.list_roles(session)


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(data: RoleCreate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.create_role(session, user, data)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: int, data: RoleUpdate, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    return auth_service.update_role(session, user, role_id, data)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(role_id: int, user: AppUser = Depends(current_user), session: Session = Depends(get_db)):
    auth_service.delete_role(session, user, role_id)
    return Response(status_code=204)
