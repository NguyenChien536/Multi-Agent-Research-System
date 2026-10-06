from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Any

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.core.security import get_password_hash

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Register a user account. This endpoint does not issue an auth token."""
    # 1. Kiểm tra email đã tồn tại chưa
    result_email = await db.execute(select(User).where(User.email == user_in.email))
    if result_email.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được đăng ký. Vui lòng sử dụng email khác."
        )

    # 2. Kiểm tra username đã tồn tại chưa
    result_username = await db.execute(select(User).where(User.username == user_in.username))
    if result_username.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username này đã tồn tại. Vui lòng chọn username khác."
        )

    # 3. Hash mật khẩu và lưu vào DB
    hashed_password = get_password_hash(user_in.password)

    db_user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=hashed_password
    )

    db.add(db_user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username is already registered.",
        ) from exc
    await db.refresh(db_user)

    return db_user
