from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..db import get_db
from ..models import User
from ..schemas import TheaterOut, UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/me/theaters", response_model=list[TheaterOut])
def read_my_theaters(user: CurrentUser) -> list[TheaterOut]:
    return [TheaterOut.model_validate(theater) for theater in user.theaters]


@router.get("/users", response_model=list[UserOut])
def list_users(db: Annotated[Session, Depends(get_db)]) -> list[UserOut]:
    """Unauthenticated on purpose: the UI needs the list to pick a session user."""
    users = db.scalars(select(User).order_by(User.name)).all()
    return [UserOut.model_validate(user) for user in users]
