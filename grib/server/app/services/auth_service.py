from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, Unauthorized
from app.core.permissions import OWNER_ROLE, PERMISSIONS, ensure_admin
from app.core.security import create_token, decode_token, hash_password, password_version, verify_password
from app.models import AppUser, Role, RolePermission
from app.repositories import MemberRepo, ProjectRepo, RoleRepo, UserRepo
from app.schemas.auth import (
    ChangePasswordRequest,
    MeOut,
    ProjectAccess,
    RoleCreate,
    RoleOut,
    RoleUpdate,
    TokenOut,
    UserCreate,
    UserOut,
    UserUpdate,
)


def login(session: Session, login_: str, password: str) -> TokenOut:
    user = UserRepo(session).by_login(login_.strip())
    if user is None or not verify_password(password, user.password_hash):
        raise Unauthorized("Неверный логин или пароль")
    if user.is_blocked:
        raise Unauthorized("Пользователь заблокирован")
    return TokenOut(token=create_token(user.id, user.password_hash), user=UserOut.model_validate(user))


def user_from_token(session: Session, token: str | None) -> AppUser:
    decoded = decode_token(token) if token else None
    user = UserRepo(session).get(decoded[0]) if decoded else None
    if user is None or password_version(user.password_hash) != decoded[1]:
        raise Unauthorized("Требуется вход в систему")
    if user.is_blocked:
        raise Unauthorized("Пользователь заблокирован")
    return user


def me(session: Session, user: AppUser) -> MeOut:
    projects = []
    if user.is_admin:
        for p in ProjectRepo(session).visible_for(user):
            member = MemberRepo(session).find(p.id, user.id)
            projects.append(
                ProjectAccess(id=p.id, name=p.name, role=member.role.name if member else None, permissions=sorted(PERMISSIONS))
            )
    else:
        for m in MemberRepo(session).for_user(user.id):
            project = ProjectRepo(session).get(m.project_id)
            projects.append(
                ProjectAccess(id=m.project_id, name=project.name, role=m.role.name, permissions=sorted(m.role.codes))
            )
        projects.sort(key=lambda p: p.name)
    return MeOut(user=UserOut.model_validate(user), projects=projects)


def change_password(session: Session, user: AppUser, data: ChangePasswordRequest) -> TokenOut:
    if not verify_password(data.old_password, user.password_hash):
        raise BadRequest("Текущий пароль указан неверно")
    user.password_hash = hash_password(data.new_password)
    session.commit()
    return TokenOut(token=create_token(user.id, user.password_hash), user=UserOut.model_validate(user))


def list_users(session: Session, actor: AppUser, q: str = "") -> list[AppUser]:
    ensure_admin(actor)
    return UserRepo(session).search(q)


def directory(session: Session, q: str = "") -> list[AppUser]:
    return [u for u in UserRepo(session).search(q) if not u.is_blocked]


def create_user(session: Session, actor: AppUser, data: UserCreate) -> AppUser:
    ensure_admin(actor)
    repo = UserRepo(session)
    if repo.by_login(data.login):
        raise Conflict(f"Логин «{data.login}» уже занят")
    user = repo.add(
        AppUser(
            login=data.login,
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            is_admin=data.is_admin,
            can_create_projects=data.can_create_projects or data.is_admin,
        )
    )
    session.commit()
    return user


def update_user(session: Session, actor: AppUser, user_id: int, data: UserUpdate) -> AppUser:
    ensure_admin(actor)
    repo = UserRepo(session)
    user = repo.get_or_404(user_id)
    fields = data.model_dump(exclude_unset=True)
    losing_admin = (fields.get("is_admin") is False or fields.get("is_blocked") is True) and user.is_admin
    if losing_admin and not user.is_blocked and repo.count_admins() <= 1:
        raise BadRequest("Нельзя лишить прав или заблокировать последнего администратора")
    if user.id == actor.id and fields.get("is_blocked"):
        raise BadRequest("Нельзя заблокировать самого себя")
    for key in ("full_name", "is_admin", "can_create_projects", "is_blocked"):
        if fields.get(key) is not None:
            setattr(user, key, fields[key])
    if fields.get("password"):
        user.password_hash = hash_password(fields["password"])
    session.commit()
    return user


def delete_user(session: Session, actor: AppUser, user_id: int) -> None:
    ensure_admin(actor)
    repo = UserRepo(session)
    user = repo.get_or_404(user_id)
    if user.id == actor.id:
        raise BadRequest("Нельзя удалить самого себя")
    owner = RoleRepo(session).by_name(OWNER_ROLE)
    members = MemberRepo(session)
    sole = [
        ProjectRepo(session).get(m.project_id).name
        for m in members.for_user(user.id)
        if owner and m.role_id == owner.id and members.count_role(m.project_id, owner.id) <= 1
    ]
    if sole:
        raise BadRequest(f"Пользователь — единственный владелец проектов: {', '.join(sole)}. Сначала назначьте им другого владельца")
    if user.is_admin and not user.is_blocked and repo.count_admins() <= 1:
        raise BadRequest("Нельзя удалить последнего администратора")
    repo.delete(user)
    session.commit()


def _role_out(role: Role, counts: dict[int, int]) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_builtin=role.is_builtin,
        permissions=sorted(role.codes),
        members=counts.get(role.id, 0),
    )


def _check_codes(codes: list[str]) -> list[str]:
    unknown = [c for c in codes if c not in PERMISSIONS]
    if unknown:
        raise BadRequest(f"Неизвестные права: {', '.join(unknown)}")
    return sorted(set(codes))


def list_roles(session: Session) -> list[RoleOut]:
    repo = RoleRepo(session)
    counts = repo.member_counts()
    return [_role_out(r, counts) for r in repo.all()]


def create_role(session: Session, actor: AppUser, data: RoleCreate) -> RoleOut:
    ensure_admin(actor)
    repo = RoleRepo(session)
    if repo.by_name(data.name):
        raise Conflict(f"Роль «{data.name}» уже существует")
    role = Role(name=data.name, description=data.description, is_builtin=False)
    role.permissions = [RolePermission(permission_code=c) for c in _check_codes(data.permissions)]
    repo.add(role)
    session.commit()
    return _role_out(role, {})


def update_role(session: Session, actor: AppUser, role_id: int, data: RoleUpdate) -> RoleOut:
    ensure_admin(actor)
    repo = RoleRepo(session)
    role = repo.get_or_404(role_id)
    if data.name is not None and data.name != role.name:
        if role.is_builtin:
            raise BadRequest("Встроенную роль нельзя переименовать")
        if repo.by_name(data.name):
            raise Conflict(f"Роль «{data.name}» уже существует")
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        codes = _check_codes(data.permissions)
        current = {p.permission_code: p for p in role.permissions}
        role.permissions = [current.get(c) or RolePermission(permission_code=c) for c in codes]
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Роль с таким именем уже существует") from exc
    return _role_out(role, repo.member_counts())


def delete_role(session: Session, actor: AppUser, role_id: int) -> None:
    ensure_admin(actor)
    repo = RoleRepo(session)
    role = repo.get_or_404(role_id)
    if role.is_builtin:
        raise BadRequest("Встроенную роль удалить нельзя")
    if repo.member_counts().get(role.id):
        raise BadRequest("Роль назначена участникам проектов. Сначала смените им роль")
    repo.delete(role)
    session.commit()
