from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

Login = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_.\-@]+$")
Password = Field(min_length=4, max_length=72)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    login: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Password


class UserOut(ORM):
    id: int
    login: str
    full_name: str
    is_admin: bool
    can_create_projects: bool
    is_blocked: bool
    created_at: datetime


class UserBrief(ORM):
    id: int
    login: str
    full_name: str


class TokenOut(BaseModel):
    token: str
    user: UserOut


class ProjectAccess(BaseModel):
    id: int
    name: str
    role: str | None
    permissions: list[str]


class MeOut(BaseModel):
    user: UserOut
    projects: list[ProjectAccess]


class UserCreate(BaseModel):
    login: str = Login
    full_name: str = Field(default="", max_length=200)
    password: str = Password
    is_admin: bool = False
    can_create_projects: bool = False


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    is_admin: bool | None = None
    can_create_projects: bool | None = None
    is_blocked: bool | None = None
    password: str | None = Field(default=None, min_length=4, max_length=72)


class PermissionOut(ORM):
    code: str
    description: str


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    is_builtin: bool
    permissions: list[str]
    members: int = 0


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=300)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    permissions: list[str] | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    created_by: UserBrief | None
    role: str | None
    permissions: list[str]
    counts: dict[str, int] = Field(default_factory=dict)


class MemberCreate(BaseModel):
    user_id: int
    role_id: int


class MemberUpdate(BaseModel):
    role_id: int


class MemberOut(BaseModel):
    id: int
    user: UserBrief
    role_id: int
    role: str
