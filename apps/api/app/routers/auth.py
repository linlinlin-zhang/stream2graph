from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AdminUser
from app.schemas import AdminIdentity, AdminLoginRequest
from app.security import decode_session, encode_session, verify_password


COOKIE_NAME = "s2g_admin_session"
router = APIRouter(prefix="/auth", tags=["auth"])


def get_current_admin(
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> AdminUser:
    if not session_token:
        raise HTTPException(status_code=401, detail="not authenticated")
    payload = decode_session(session_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid session")
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.get("username")))
    if user is None:
        raise HTTPException(status_code=401, detail="admin user not found")
    return user


@router.post("/login", response_model=AdminIdentity)
def login(payload: AdminLoginRequest, response: Response, db: Session = Depends(get_db)) -> AdminIdentity:
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = encode_session({"username": user.username})
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    return AdminIdentity(username=user.username, display_name=user.display_name)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=AdminIdentity)
def me(
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> AdminIdentity:
    user = get_current_admin(db=db, session_token=session_token)
    return AdminIdentity(username=user.username, display_name=user.display_name)
