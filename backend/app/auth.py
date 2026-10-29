"""JWT auth + bcrypt-hashed demo users (ported from api/index.py:43-58, 117-143)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import bcrypt
import jwt

from .config import get_settings


@dataclass(frozen=True)
class DemoUser:
    id: str
    email: str
    name: str
    role: str
    pw_hash: bytes

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role}


_USERS: list[DemoUser] = [
    DemoUser(
        id="1",
        email="admin@neuratriage.com",
        name="Admin",
        role="admin",
        pw_hash=bcrypt.hashpw(b"demo1234", bcrypt.gensalt()),
    ),
    DemoUser(
        id="2",
        email="doctor@neuratriage.com",
        name="Xuan Que",
        role="clinician",
        pw_hash=bcrypt.hashpw(b"demo1234", bcrypt.gensalt()),
    ),
]


def find_user_by_email(email: str) -> Optional[DemoUser]:
    target = (email or "").strip().lower()
    return next((u for u in _USERS if u.email == target), None)


def find_user_by_id(user_id: str) -> Optional[DemoUser]:
    return next((u for u in _USERS if u.id == user_id), None)


def verify_password(password: str, user: DemoUser) -> bool:
    if not password:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), user.pw_hash)


def issue_token(user: DemoUser) -> tuple[str, int]:
    settings = get_settings()
    exp = int(time.time()) + settings.jwt_expires_hours * 3600
    token = jwt.encode(
        {"sub": user.id, "exp": exp},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, exp


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
