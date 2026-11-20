import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def password_version(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_token(user_id: int, password_hash: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "pv": password_version(password_hash),
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_token(token: str) -> tuple[int, str] | None:
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        return int(data["sub"]), str(data["pv"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
