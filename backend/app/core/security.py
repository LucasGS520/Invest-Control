"""Utilitários de segurança: hashing de senhas e geração/validação de tokens JWT."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------- Senhas ----------


def hash_password(plain: str) -> str:
    """Retorna o hash bcrypt da senha fornecida."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash armazenado."""
    return _pwd_context.verify(plain, hashed)


# ---------- JWT ----------


def create_access_token(subject: str | int) -> str:
    """Gera um JWT de acesso com expiração configurada em settings."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str:
    """Decodifica o JWT e retorna o subject (user id).

    Lança JWTError em caso de token inválido ou expirado.
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    sub: str | None = payload.get("sub")
    if sub is None:
        raise JWTError("Token sem subject.")
    return sub
