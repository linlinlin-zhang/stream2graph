from __future__ import annotations

from typing import Any

from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

from app.config import get_settings


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _serializer() -> URLSafeSerializer:
    settings = get_settings()
    return URLSafeSerializer(settings.session_secret, salt="stream2graph-admin-session")


def encode_session(payload: dict[str, Any]) -> str:
    return _serializer().dumps(payload)


def decode_session(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        return _serializer().loads(token)
    except BadSignature:
        return None
