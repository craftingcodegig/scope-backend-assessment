from __future__ import annotations

from fastapi import APIRouter

from ..auth import CurrentUser
from ..schemas import TheaterOut, UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/me/theaters", response_model=list[TheaterOut])
def read_my_theaters(user: CurrentUser) -> list[TheaterOut]:
    return [TheaterOut.model_validate(theater) for theater in user.theaters]
