import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.core.errors import QueryError

_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(f"grib-crypto:{settings.secret_key}".encode()).digest()))


def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode() if plain else ""


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise QueryError("Не удалось расшифровать пароль источника. Возможно, изменился GRIB_SECRET_KEY") from exc
