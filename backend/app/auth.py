from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

# Authentication is intentionally minimal: the frontend picks a user and sends
# its id on every request. Authorization (role and theater membership) is
# still enforced server-side so the API cannot be bypassed by the UI.


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    x_user_id: Annotated[str | None, Header()] = None,
) -> User:
    if not x_user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-User-Id header")
    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
