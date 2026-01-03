from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.schemas import UserOut
from app.utils import normalize_mongo

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return normalize_mongo(user)
