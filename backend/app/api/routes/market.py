"""Endpoints de dados de mercado: cotações, dividendos, DY e preço-teto Barsi."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models.asset import Asset
from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.db.models.portfolio_asset import PortfolioAsset
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.market import AssetDetailOut, AssetSearchResult, CeilingOut, DividendOut, DYHistoryOut, DYOut, QuoteOut, UserPositionContext
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


@router.get(
    "/search",
    response_model=list[AssetSearchResult],
    summary="Busca ativo por ticker ou nome",
)
async def search_assets(
    q: str = Query(..., min_length=2, description="Ticker ou fragmento do nome"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AssetSearchResult]:
    """Busca ativos cadastrados localmente por ticker ou nome (case-insensitive).
    Retorna cotação do cache quando disponível.
    """
    q_upper = q.upper()
    result = await db.execute(
        select(Asset).where(
            Asset.is_active == True,  # noqa: E712
            (Asset.ticker.ilike(f"%{q}%")) | (Asset.name.ilike(f"%{q}%")),
        ).limit(20)
    )
    assets = list(result.scalars().all())

    tickers = [a.ticker for a in assets]
    quotes: dict[str, MarketQuote] = {}
    if tickers:
        q_result = await db.execute(select(MarketQuote).where(MarketQuote.ticker.in_(tickers)))
        quotes = {row.ticker: row for row in q_result.scalars().all()}

    return [
        AssetSearchResult(
            ticker=a.ticker,
            name=a.name,
            sector=a.sector,
            asset_type=a.asset_type,
            price=Decimal(str(quotes[a.ticker].price)) if a.ticker in quotes else None,
            change_percent=Decimal(str(quotes[a.ticker].change_percent)) if a.ticker in quotes and quotes[a.ticker].change_percent is not None else None,
        )
        for a in assets
    ]


@router.get(
    "/asset/{ticker}",
    response_model=AssetDetailOut,
    summary="Detalhe do ativo com contexto do usuário",
)
async def get_asset_detail(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssetDetailOut:
    """Retorna metadados do ativo, cotação atual e posição do usuário em todas as carteiras."""
    ticker = ticker.upper()

    asset_result = await db.execute(select(Asset).where(Asset.ticker == ticker))
    asset = asset_result.scalar_one_or_none()

    if asset is None:
        from app.services.asset_service import get_or_create_asset
        asset = await get_or_create_asset(db, ticker)
        await db.commit()
        await db.refresh(asset)

    quote_result = await db.execute(select(MarketQuote).where(MarketQuote.ticker == ticker))
    quote = quote_result.scalar_one_or_none()
    price = Decimal(str(quote.price)) if quote else None
    change_pct = Decimal(str(quote.change_percent)) if quote and quote.change_percent is not None else None
    volume = Decimal(str(quote.volume)) if quote and quote.volume is not None else None

    pos_result = await db.execute(
        select(PortfolioAsset)
        .join(PortfolioAsset.portfolio)
        .where(
            PortfolioAsset.asset_id == asset.id,
            PortfolioAsset.quantity > 0,
        )
    )
    raw_positions = list(pos_result.scalars().all())

    positions: list[UserPositionContext] = []
    for pos in raw_positions:
        from app.db.models.portfolio import Portfolio as PortfolioModel
        port_result = await db.execute(
            select(PortfolioModel).where(
                PortfolioModel.id == pos.portfolio_id,
                PortfolioModel.user_id == user.id,
            )
        )
        portfolio = port_result.scalar_one_or_none()
        if portfolio is None:
            continue

        avg = Decimal(str(pos.avg_price))
        qty = Decimal(str(pos.quantity))
        invested = qty * avg
        current_value = qty * price if price is not None else None
        return_pct = (
            ((current_value - invested) / invested * Decimal("100")).quantize(Decimal("0.01"))
            if current_value is not None and invested > 0
            else None
        )
        positions.append(
            UserPositionContext(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio.name,
                quantity=pos.quantity,
                avg_price=avg,
                current_value=current_value,
                return_pct=return_pct,
            )
        )

    div_result = await db.execute(
        select(Dividend).where(Dividend.ticker == ticker).order_by(Dividend.ex_date.desc()).limit(12)
    )
    dividends = list(div_result.scalars().all())
    total_divs: Decimal | None = None
    if positions and dividends:
        total_qty = sum(p.quantity for p in raw_positions)
        total_divs = sum(Decimal(str(d.value)) for d in dividends) * Decimal(str(total_qty))

    return AssetDetailOut(
        ticker=asset.ticker,
        name=asset.name,
        sector=asset.sector,
        asset_type=asset.asset_type,
        price=price,
        change_percent=change_pct,
        volume=volume,
        positions=positions,
        total_dividends_received=total_divs,
    )
