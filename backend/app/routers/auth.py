"""POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout
(ported from api/index.py:117-143).
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel

from ..auth import DemoUser, find_user_by_email, issue_token, verify_password
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..services.rate_limit import login_limiter


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(request: Request, body: LoginRequest = Body(...), _rl: None = Depends(login_limiter)):
    user = find_user_by_email(body.email)
    if not user or not verify_password(body.password, user):
        raise EnvelopeError("Invalid email or password", "INVALID_CREDENTIALS", 401)
    token, exp = issue_token(user)
    return ok({"access_token": token, "expires_at": exp, "user": user.public()})


@router.get("/me")
def me(user: DemoUser = Depends(get_current_user)):
    return ok(user.public())


@router.post("/logout")
def logout(user: DemoUser = Depends(get_current_user)):
    return ok({"message": "Logged out"})
