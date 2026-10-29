"""FastAPI dependencies — auth extraction (ported from api/index.py:89-104)."""
from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Depends, Header

from .auth import DemoUser, decode_token, find_user_by_id
from .envelope import EnvelopeError


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise EnvelopeError("Missing token", "MISSING_TOKEN", 401)
    token = authorization[7:]
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise EnvelopeError("Token expired", "TOKEN_EXPIRED", 401)
    except jwt.InvalidTokenError:
        raise EnvelopeError("Invalid token", "INVALID_TOKEN", 401)
    return str(payload.get("sub", ""))


def get_current_user(user_id: str = Depends(get_current_user_id)) -> DemoUser:
    user = find_user_by_id(user_id)
    if not user:
        raise EnvelopeError("User not found", "USER_NOT_FOUND", 404)
    return user
