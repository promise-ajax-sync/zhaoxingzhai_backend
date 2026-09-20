from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    bearer_token,
    create_access_token,
    decode_access_token,
    hash_password,
    new_refresh_token,
    refresh_token_hash,
    verify_password,
)
from app.core.config import Settings
from app.models import Case, DivinationRecord, EmailToken, RefreshToken, User
from app.schemas.auth import TokenResponse, UserResponse
from app.services.record_service import device_hash, get_or_create_user, require_device_id


def user_response(user: User) -> UserResponse:
    if user.email is None:
        raise HTTPException(status_code=401, detail="当前用户尚未注册")
    return UserResponse(
        id=user.id,
        email=user.email,
        displayName=user.display_name,
        avatarUrl=user.avatar_url,
        emailVerified=user.email_verified,
        isAnonymous=user.is_anonymous,
    )


async def issue_token_pair(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> TokenResponse:
    access_token, expires_at = create_access_token(str(user.id), settings)
    raw_refresh_token = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_token_hash(raw_refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.app_refresh_token_days),
        )
    )
    await session.commit()
    return TokenResponse(
        accessToken=access_token,
        refreshToken=raw_refresh_token,
        tokenType="Bearer",
        accessExpiresAt=expires_at,
        user=user_response(user),
    )


async def authenticated_user(
    session: AsyncSession,
    token: str,
    settings: Settings,
) -> User:
    claims = decode_access_token(token, settings)
    try:
        user_id = UUID(claims["sub"])
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="登录凭证无效") from error
    user = await session.get(User, user_id)
    if user is None or not user.is_active or user.is_anonymous:
        raise HTTPException(status_code=401, detail="登录用户不存在或已停用")
    return user


async def require_authenticated_user(
    session: AsyncSession,
    request: Request,
    settings: Settings,
) -> User:
    token = bearer_token(request)
    if token is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return await authenticated_user(session, token, settings)


async def request_user(
    session: AsyncSession,
    request: Request,
    settings: Settings,
) -> User:
    token = bearer_token(request)
    if token is not None:
        return await authenticated_user(session, token, settings)
    return await get_or_create_user(session, require_device_id(request), settings)


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str | None,
    request: Request,
    settings: Settings,
) -> User:
    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    device_id = request.headers.get("x-device-id", "").strip()
    user: User | None = None
    if device_id:
        require_device_id(request)
        hashed = device_hash(device_id, settings.app_device_hash_secret)
        user = await session.scalar(select(User).where(User.device_id_hash == hashed))
        if user is not None and not user.is_anonymous:
            user = None

    if user is None:
        user = User(is_anonymous=False, is_active=True)
        session.add(user)

    user.email = email
    user.password_hash = hash_password(password)
    user.display_name = display_name.strip() if display_name and display_name.strip() else None
    user.is_anonymous = False
    await session.flush()
    return user


async def login_user(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码不正确")
    return user


async def merge_anonymous_device_data(
    session: AsyncSession,
    request: Request,
    account: User,
    settings: Settings,
) -> None:
    device_id = request.headers.get("x-device-id", "").strip()
    if not device_id:
        return
    require_device_id(request)
    hashed = device_hash(device_id, settings.app_device_hash_secret)
    anonymous = await session.scalar(select(User).where(User.device_id_hash == hashed))
    if anonymous is None or not anonymous.is_anonymous or anonymous.id == account.id:
        return

    account_cases = {
        item.client_id: item
        for item in (await session.scalars(select(Case).where(Case.user_id == account.id))).all()
    }
    anonymous_cases = (
        await session.scalars(select(Case).where(Case.user_id == anonymous.id))
    ).all()
    case_targets: dict[object, object] = {}
    for case in anonymous_cases:
        existing = account_cases.get(case.client_id)
        if existing is None:
            case.user_id = account.id
            account_cases[case.client_id] = case
            case_targets[case.id] = case.id
        else:
            case_targets[case.id] = existing.id

    account_record_ids = set(
        (await session.scalars(select(DivinationRecord.client_record_id).where(
            DivinationRecord.user_id == account.id
        ))).all()
    )
    anonymous_records = (
        await session.scalars(select(DivinationRecord).where(DivinationRecord.user_id == anonymous.id))
    ).all()
    for record in anonymous_records:
        if record.client_record_id in account_record_ids:
            await session.delete(record)
            continue
        record.user_id = account.id
        if record.case_id in case_targets:
            record.case_id = case_targets[record.case_id]
        account_record_ids.add(record.client_record_id)

    await session.flush()
    await session.execute(delete(User).where(User.id == anonymous.id))
    await session.flush()
    if account.device_id_hash is None:
        account.device_id_hash = hashed


async def rotate_refresh_token(
    session: AsyncSession,
    raw_token: str,
    settings: Settings,
) -> TokenResponse:
    token = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == refresh_token_hash(raw_token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise HTTPException(status_code=401, detail="刷新凭证无效或已过期")
    user = await session.get(User, token.user_id)
    if user is None or not user.is_active or user.is_anonymous:
        raise HTTPException(status_code=401, detail="登录用户不存在或已停用")
    token.revoked_at = now
    await session.flush()
    return await issue_token_pair(session, user, settings)


async def revoke_refresh_token(session: AsyncSession, raw_token: str) -> None:
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == refresh_token_hash(raw_token))
    )
    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        await session.commit()


async def create_email_token(
    session: AsyncSession,
    user: User,
    purpose: str,
    settings: Settings,
) -> str:
    raw_token = new_refresh_token()
    now = datetime.now(UTC)
    existing = (
        await session.scalars(
            select(EmailToken).where(
                EmailToken.user_id == user.id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
        )
    ).all()
    for token in existing:
        token.used_at = now
    session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=refresh_token_hash(raw_token),
            expires_at=now + timedelta(minutes=settings.app_email_token_minutes),
        )
    )
    await session.commit()
    return raw_token


async def consume_email_token(
    session: AsyncSession,
    raw_token: str,
    purpose: str,
) -> tuple[EmailToken, User]:
    token = await session.scalar(
        select(EmailToken)
        .where(
            EmailToken.token_hash == refresh_token_hash(raw_token),
            EmailToken.purpose == purpose,
        )
        .with_for_update()
    )
    now = datetime.now(UTC)
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="用户不存在或已停用")
    token.used_at = now
    return token, user
