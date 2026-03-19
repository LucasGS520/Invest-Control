"""Endpoints de autenticação: registro, login e perfil."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import RegisterOut, TokenOut, UserOut, UserRegister
from app.services.auth_service import authenticate_user, create_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=RegisterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra novo usuário",
)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)) -> RegisterOut:
    """Cria conta e retorna token de acesso imediatamente."""
    user = await create_user(db, data)
    token = create_access_token(user.id)
    return RegisterOut(
        user=UserOut.model_validate(user),
        token=TokenOut(access_token=token),
    )


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Autentica usuário (OAuth2)",
)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    """Recebe username (e-mail) e password via form-data e retorna JWT."""
    user = await authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut, summary="Retorna usuário autenticado")
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
