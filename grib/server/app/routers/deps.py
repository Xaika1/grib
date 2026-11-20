from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import AppUser
from app.services import auth_service

_bearer = HTTPBearer(auto_error=False)


def get_db(session: Session = Depends(get_session)) -> Session:
    return session


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_db),
) -> AppUser:
    return auth_service.user_from_token(session, cred.credentials if cred else None)
