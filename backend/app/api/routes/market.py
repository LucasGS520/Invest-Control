"""Endpoints de dados de mercado: cotações, dividendos, DY e preço-teto Barsi."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.market import CeilingOut, DividendOut, DYHistoryOut, DYOut, QuoteOut
from app.services import market_data_service as mds
from app.services import rules_engine as re

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get(
    "/quote/{ticker}",
    response_model=QuoteOut,
    summary="Cotação atual do ativo (com cache)",
)
async def get_quote(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> QuoteOut:
    """Retorna cotação do cache ou busca na brapi.dev se expirada."""
    try:
        quote = await mds.get_quote(db, ticker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao obter cotação para '{ticker}': {exc}",
        ) from exc
    return QuoteOut.model_validate(quote)


@router.post(
    "/quote/{ticker}/refresh",
    response_model=QuoteOut,
    summary="Força atualização da cotação na API externa",
)
async def refresh_quote(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> QuoteOut:
    """Ignora o cache e busca a cotação mais recente na brapi.dev."""
    try:
        quote_data = await mds.fetch_quote_from_api(ticker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao atualizar cotação para '{ticker}': {exc}",
        ) from exc

    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.db.models.market_data import MarketQuote

    result = await db.execute(select(MarketQuote).where(MarketQuote.ticker == ticker.upper()))
    cached = result.scalar_one_or_none()

    if cached is None:
        from app.db.models.market_data import MarketQuote as MQ

        cached = MQ(ticker=ticker.upper())
        db.add(cached)

    cached.price = quote_data["price"]
    cached.change_percent = quote_data["change_percent"]
    cached.volume = quote_data["volume"]
    cached.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(cached)
    return QuoteOut.model_validate(cached)


@router.get(
    "/dividends/{ticker}",
    response_model=list[DividendOut],
    summary="Histórico de proventos do ativo",
)
async def get_dividends(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DividendOut]:
    """Retorna proventos do banco, sincronizando com brapi.dev se necessário."""
    try:
        dividends = await mds.get_dividends(db, ticker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao obter dividendos para '{ticker}': {exc}",
        ) from exc
    return [DividendOut.model_validate(d) for d in dividends]


@router.post(
    "/dividends/{ticker}/sync",
    response_model=dict,
    summary="Sincroniza proventos com brapi.dev",
)
async def sync_dividends(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        new_divs = await mds.sync_dividends(db, ticker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao sincronizar dividendos para '{ticker}': {exc}",
        ) from exc
    return {"ticker": ticker.upper(), "new_records": len(new_divs)}


@router.get(
    "/dy/{ticker}",
    response_model=DYOut,
    summary="Dividend Yield anualizado",
)
async def get_dy(
    ticker: str,
    months: int = Query(default=12, ge=1, le=60, description="Janela em meses para cálculo"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DYOut:
    dy = await re.calculate_dy(db, ticker, months=months)
    return DYOut(ticker=ticker.upper(), current_dy=dy, months=months)


@router.get(
    "/dy/{ticker}/history",
    response_model=DYHistoryOut,
    summary="DY anual histórico",
)
async def get_dy_history(
    ticker: str,
    years: int = Query(default=3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DYHistoryOut:
    history = await re.calculate_dy_history(db, ticker, years=years)
    return DYHistoryOut(ticker=ticker.upper(), history=history)


@router.get(
    "/ceiling/{ticker}",
    response_model=CeilingOut,
    summary="Preço-teto pelo método Barsi",
)
async def get_ceiling(
    ticker: str,
    desired_dy: Decimal = Query(
        default=Decimal("6.0"),
        gt=0,
        description="DY desejado em % (ex: 6.0 para 6%)",
    ),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CeilingOut:
    """Calcula e retorna o preço-teto Barsi e análise de oportunidade."""
    result = await re.identify_opportunity(db, ticker, desired_dy=desired_dy)
    return CeilingOut(**result)
