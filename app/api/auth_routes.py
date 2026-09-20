from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password, verify_password
from app.core.config import get_settings
from app.core.database import get_session
from app.models import RefreshToken, User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    EmailActionResponse,
    EmailTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.auth_service import (
    issue_token_pair,
    login_user,
    merge_anonymous_device_data,
    register_user,
    require_authenticated_user,
    revoke_refresh_token,
    rotate_refresh_token,
    user_response,
    consume_email_token,
    create_email_token,
)
from app.services.email_service import EmailService
from app.services.avatar_service import remove_avatar_files, save_avatar

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    settings = get_settings()
    user = await register_user(
        session,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        request=request,
        settings=settings,
    )
    return await issue_token_pair(session, user, settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    settings = get_settings()
    user = await login_user(session, payload.email, payload.password)
    await merge_anonymous_device_data(session, request, user, settings)
    return await issue_token_pair(session, user, settings)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    return await rotate_refresh_token(session, payload.refresh_token, get_settings())


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await revoke_refresh_token(session, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await require_authenticated_user(session, request, get_settings())
    return user_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateProfileRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await require_authenticated_user(session, request, get_settings())
    if "display_name" in payload.model_fields_set:
        user.display_name = payload.display_name
    if "avatar_url" in payload.model_fields_set:
        user.avatar_url = payload.avatar_url
    await session.commit()
    await session.refresh(user)
    return user_response(user)


@router.post("/avatar", response_model=UserResponse)
async def upload_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    settings = get_settings()
    user = await require_authenticated_user(session, request, settings)
    relative_url = await save_avatar(avatar, user, settings)
    user.avatar_url = f"{str(request.base_url).rstrip('/')}{relative_url}"
    await session.commit()
    await session.refresh(user)
    return user_response(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await require_authenticated_user(session, request, get_settings())
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    user.password_hash = hash_password(payload.new_password)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    settings = get_settings()
    user = await require_authenticated_user(session, request, settings)
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    user_id = user.id
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()
    remove_avatar_files(user_id, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _development_token(settings, token: str) -> str | None:
    return token if settings.app_env != "production" else None


@router.post("/request-email-verification", response_model=EmailActionResponse)
async def request_email_verification(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> EmailActionResponse:
    settings = get_settings()
    user = await require_authenticated_user(session, request, settings)
    if user.email_verified:
        return EmailActionResponse(message="邮箱已经完成验证")
    token = await create_email_token(session, user, "verify_email", settings)
    await EmailService(settings).send_code(user.email, purpose="verify_email", code=token)
    return EmailActionResponse(
        message="验证码已发送，请检查邮箱",
        developmentToken=_development_token(settings, token),
    )


@router.post("/confirm-email", response_model=UserResponse)
async def confirm_email(
    payload: EmailTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    current = await require_authenticated_user(session, request, get_settings())
    _, user = await consume_email_token(session, payload.token, "verify_email")
    if user.id != current.id:
        raise HTTPException(status_code=400, detail="验证码与当前账号不匹配")
    user.email_verified = True
    await session.commit()
    await session.refresh(user)
    return user_response(user)


@router.post("/forgot-password", response_model=EmailActionResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> EmailActionResponse:
    settings = get_settings()
    user = await session.scalar(select(User).where(User.email == payload.email))
    development_token = None
    if user is not None and user.is_active and not user.is_anonymous:
        token = await create_email_token(session, user, "reset_password", settings)
        await EmailService(settings).send_code(
            user.email,
            purpose="reset_password",
            code=token,
        )
        development_token = _development_token(settings, token)
    return EmailActionResponse(
        message="如果该邮箱已注册，重置验证码将发送到邮箱",
        developmentToken=development_token,
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    _, user = await consume_email_token(session, payload.token, "reset_password")
    user.password_hash = hash_password(payload.new_password)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
