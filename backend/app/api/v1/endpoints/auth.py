from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from typing import Any
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserDeletionRequest, UserLogin, UserProfileUpdate, UserResponse
from app.core.security import create_access_token, get_password_hash, verify_password
from app.api.deps import get_current_user

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


@router.post("/login", response_model=TokenResponse)
async def login_user(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == credentials.email, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    changes: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Update only the signed-in account; email changes require reauthentication."""
    user = await db.scalar(select(User).where(User.id == current_user.id, User.deleted_at.is_(None)).with_for_update())
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    if "email" in changes.model_fields_set and changes.email != user.email:
        if not changes.current_password or not verify_password(changes.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current password is required to change your email.",
            )

    values = changes.model_dump(exclude_unset=True, exclude={"current_password"})
    conflicts = []
    if "username" in values:
        conflicts.append(User.username == values["username"])
    if "email" in values:
        conflicts.append(User.email == values["email"])
    if conflicts:
        duplicate = await db.scalar(select(User.id).where(User.id != user.id, or_(*conflicts)).limit(1))
        if duplicate:
            raise HTTPException(status_code=409, detail="Email or username is already registered.")
    for name, value in values.items():
        setattr(user, name, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email or username is already registered.") from exc
    await db.refresh(user)
    return user


@router.delete("/me", status_code=status.HTTP_202_ACCEPTED)
async def delete_me(
    confirmation: UserDeletionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disable access immediately; the durable cleanup loop removes owned data."""
    user = await db.scalar(select(User).where(User.id == current_user.id, User.deleted_at.is_(None)).with_for_update())
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    if not verify_password(confirmation.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Current password is incorrect.")
    user.deleted_at = datetime.now(timezone.utc)
    user.model_connection = None
    await db.commit()
    return {"status": "DELETING", "message": "Account access revoked; private data cleanup queued."}
