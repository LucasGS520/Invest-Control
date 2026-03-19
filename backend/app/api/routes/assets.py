"""Endpoints para gerenciamento de ativos (ações e FIIs)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models.asset import Asset
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.asset import AssetCreate, AssetOut

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get("/", response_model=list[AssetOut], summary="Lista todos os ativos")
async def list_assets(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Asset]:
    result = await db.execute(select(Asset).where(Asset.is_active == True).order_by(Asset.ticker))  # noqa: E712
    return list(result.scalars().all())


@router.post(
    "/",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra novo ativo",
)
async def create_asset(
    data: AssetCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Asset:
    # Verifica ticker duplicado
    existing = await db.execute(select(Asset).where(Asset.ticker == data.ticker.upper()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ativo '{data.ticker}' já cadastrado.",
        )
    asset = Asset(
        ticker=data.ticker.upper(),
        name=data.name,
        sector=data.sector,
        asset_type=data.asset_type,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.get("/{ticker}", response_model=AssetOut, summary="Busca ativo pelo ticker")
async def get_asset(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Asset:
    result = await db.execute(select(Asset).where(Asset.ticker == ticker.upper()))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ativo não encontrado.")
    return asset
