from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, Forbidden
from app.core.permissions import OWNER_ROLE, ensure, user_permissions
from app.models import AppUser, Project, ProjectMember
from app.repositories import MemberRepo, ProjectRepo, RoleRepo, UserRepo
from app.schemas.auth import MemberCreate, MemberOut, MemberUpdate, ProjectCreate, ProjectOut, ProjectUpdate, UserBrief


def _out(session: Session, project: Project, user: AppUser) -> ProjectOut:
    member = MemberRepo(session).find(project.id, user.id)
    author = UserRepo(session).get(project.created_by) if project.created_by else None
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        created_by=UserBrief.model_validate(author) if author else None,
        role=member.role.name if member else ("Администратор" if user.is_admin else None),
        permissions=sorted(user_permissions(session, user, project.id)),
        counts=ProjectRepo(session).counts(project.id),
    )


def list_projects(session: Session, user: AppUser) -> list[ProjectOut]:
    return [_out(session, p, user) for p in ProjectRepo(session).visible_for(user)]


def get_project(session: Session, user: AppUser, project_id: int) -> ProjectOut:
    project = ProjectRepo(session).get_or_404(project_id)
    if not user.is_admin and MemberRepo(session).find(project_id, user.id) is None:
        raise Forbidden("Вы не участник этого проекта")
    return _out(session, project, user)


def create_project(session: Session, user: AppUser, data: ProjectCreate) -> ProjectOut:
    if not (user.is_admin or user.can_create_projects):
        raise Forbidden("Нет права создавать проекты")
    repo = ProjectRepo(session)
    if repo.by_name(data.name):
        raise Conflict(f"Проект «{data.name}» уже существует")
    project = repo.add(Project(name=data.name, description=data.description, created_by=user.id))
    owner = RoleRepo(session).by_name(OWNER_ROLE)
    if owner is None:
        raise BadRequest("Не найдена встроенная роль владельца проекта")
    MemberRepo(session).add(ProjectMember(project_id=project.id, user_id=user.id, role_id=owner.id))
    session.commit()
    return _out(session, project, user)


def update_project(session: Session, user: AppUser, project_id: int, data: ProjectUpdate) -> ProjectOut:
    ensure(session, user, project_id, "project.manage")
    repo = ProjectRepo(session)
    project = repo.get_or_404(project_id)
    if data.name is not None and data.name != project.name:
        if repo.by_name(data.name):
            raise Conflict(f"Проект «{data.name}» уже существует")
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    session.commit()
    return _out(session, project, user)


def delete_project(session: Session, user: AppUser, project_id: int) -> None:
    ensure(session, user, project_id, "project.manage")
    repo = ProjectRepo(session)
    repo.delete(repo.get_or_404(project_id))
    session.commit()


def _member_out(m: ProjectMember) -> MemberOut:
    return MemberOut(id=m.id, user=UserBrief.model_validate(m.user), role_id=m.role_id, role=m.role.name)


def list_members(session: Session, user: AppUser, project_id: int) -> list[MemberOut]:
    get_project(session, user, project_id)
    return [_member_out(m) for m in MemberRepo(session).for_project(project_id)]


def _ensure_owner_left(session: Session, project_id: int, member: ProjectMember, new_role_id: int | None) -> None:
    owner = RoleRepo(session).by_name(OWNER_ROLE)
    if owner and member.role_id == owner.id and new_role_id != owner.id:
        if MemberRepo(session).count_role(project_id, owner.id) <= 1:
            raise BadRequest("В проекте должен остаться хотя бы один владелец")


def add_member(session: Session, user: AppUser, project_id: int, data: MemberCreate) -> MemberOut:
    ensure(session, user, project_id, "project.members")
    ProjectRepo(session).get_or_404(project_id)
    target = UserRepo(session).get_or_404(data.user_id)
    RoleRepo(session).get_or_404(data.role_id)
    repo = MemberRepo(session)
    if repo.find(project_id, target.id):
        raise Conflict(f"Пользователь «{target.login}» уже участник проекта")
    member = repo.add(ProjectMember(project_id=project_id, user_id=target.id, role_id=data.role_id))
    session.commit()
    session.refresh(member)
    return _member_out(member)


def update_member(session: Session, user: AppUser, project_id: int, member_id: int, data: MemberUpdate) -> MemberOut:
    ensure(session, user, project_id, "project.members")
    member = MemberRepo(session).get_or_404(member_id)
    if member.project_id != project_id:
        raise BadRequest("Участник относится к другому проекту")
    RoleRepo(session).get_or_404(data.role_id)
    _ensure_owner_left(session, project_id, member, data.role_id)
    member.role_id = data.role_id
    session.commit()
    session.refresh(member)
    return _member_out(member)


def remove_member(session: Session, user: AppUser, project_id: int, member_id: int) -> None:
    ensure(session, user, project_id, "project.members")
    repo = MemberRepo(session)
    member = repo.get_or_404(member_id)
    if member.project_id != project_id:
        raise BadRequest("Участник относится к другому проекту")
    _ensure_owner_left(session, project_id, member, None)
    repo.delete(member)
    session.commit()
