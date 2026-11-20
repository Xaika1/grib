import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import BUILTIN_ROLES, PERMISSIONS
from app.core.security import hash_password
from app.models import AppUser, Permission, Role, RolePermission
from app.repositories import PermissionRepo, RoleRepo, UserRepo

log = logging.getLogger("grib.bootstrap")


def seed(session: Session) -> None:
    perms = PermissionRepo(session)
    for code, description in PERMISSIONS.items():
        existing = perms.get(code)
        if existing is None:
            session.add(Permission(code=code, description=description))
        elif existing.description != description:
            existing.description = description
    for stale in perms.all():
        if stale.code not in PERMISSIONS:
            session.delete(stale)
    session.flush()

    roles = RoleRepo(session)
    for name, (description, codes) in BUILTIN_ROLES.items():
        role = roles.by_name(name)
        if role is None:
            role = Role(name=name, description=description, is_builtin=True)
            role.permissions = [RolePermission(permission_code=c) for c in sorted(codes)]
            session.add(role)

    users = UserRepo(session)
    if users.count() == 0:
        session.add(
            AppUser(
                login=settings.admin_login,
                full_name="Администратор",
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
                can_create_projects=True,
            )
        )
        log.warning("Создан администратор «%s». Смените пароль после первого входа.", settings.admin_login)
    session.commit()
