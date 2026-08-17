from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.infra.rate_limit import check_rate_limit
from app.infra.redis import get_redis
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from app.modules.auth.service import (
    authenticate,
    issue_token_pair,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.observability.metrics import RATE_LIMIT_REJECTIONS

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _issue_login_tokens(
    request: Request,
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> TokenPair:
    redis = await get_redis()
    try:
        client_ip = request.client.host if request.client else "unknown"
        result = await check_rate_limit(
            redis,
            f"ratelimit:login:{client_ip}",
            limit=10,
            window_seconds=60,
        )
    finally:
        await redis.aclose()
    if not result.allowed:
        RATE_LIMIT_REJECTIONS.labels(scope="login_ip").inc()
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts",
            headers={"Retry-After": str(result.retry_after)},
        )
    user = await authenticate(session, email, password)
    return await issue_token_pair(session, user)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await register_user(session, payload)
    return UserResponse(id=str(user.id), email=user.email, full_name=user.full_name)


@router.post("/login", response_model=TokenPair)
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    return await _issue_login_tokens(
        request,
        session,
        email=str(payload.email),
        password=payload.password,
    )


@router.post(
    "/token",
    response_model=TokenPair,
    summary="OAuth2 password-flow token endpoint",
)
async def oauth2_token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    return await _issue_login_tokens(
        request,
        session,
        email=form.username,
        password=form.password,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    return await rotate_refresh_token(session, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    await revoke_refresh_token(session, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=str(user.id), email=user.email, full_name=user.full_name)
