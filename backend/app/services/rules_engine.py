"""Motor de regras financeiras: DY histórico e preço-teto (método Barsi).

Implementa os cálculos do FR4 do SRS:
- Dividend Yield atual e histórico
- Preço-teto = média_dividendo_anual / DY_desejado
- Identificação de oportunidades (abaixo do teto, queda recente, DY alto)
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote

# ──────────────────────────────────────────────────────────────────────────────
# Dividend Yield
# ──────────────────────────────────────────────────────────────────────────────


async def calculate_dy(
    db: AsyncSession,
    ticker: str,
    months: int = 12,
) -> Decimal | None:
    """Calcula o Dividend Yield anualizado do ativo.

    DY = (soma dos dividendos nos últimos `months` meses) / preço_atual * 100

    Retorna None se não houver cotação ou histórico de dividendos suficiente.
    """
    ticker = ticker.upper()

    # Preço atual
    price_result = await db.execute(
        select(MarketQuote.price).where(MarketQuote.ticker == ticker)
    )
    price_row = price_result.scalar_one_or_none()
    if price_row is None or Decimal(str(price_row)) == 0:
        return None

    price = Decimal(str(price_row))

    # Soma dos dividendos no período
    cutoff = date.today() - timedelta(days=months * 30)
    result = await db.execute(
        select(Dividend).where(
            Dividend.ticker == ticker,
            Dividend.ex_date >= cutoff,
        )
    )
    dividends = result.scalars().all()

    if not dividends:
        return None

    total = sum(Decimal(str(d.value)) for d in dividends)

    # Anualiza se o período for diferente de 12 meses
    if months != 12:
        total = total * Decimal("12") / Decimal(str(months))

    dy = (total / price * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return dy


async def calculate_dy_history(
    db: AsyncSession,
    ticker: str,
    years: int = 3,
) -> list[dict]:
    """Retorna DY anual para os últimos `years` anos.

    Cada item: {"year": int, "total_dividends": Decimal, "dy_percent": Decimal | None}
    """
    ticker = ticker.upper()

    price_result = await db.execute(
        select(MarketQuote.price).where(MarketQuote.ticker == ticker)
    )
    price_row = price_result.scalar_one_or_none()
    price = Decimal(str(price_row)) if price_row else None

    current_year = date.today().year
    history: list[dict] = []

    for year_offset in range(years):
        year = current_year - year_offset
        result = await db.execute(
            select(Dividend).where(
                Dividend.ticker == ticker,
                Dividend.ex_date >= date(year, 1, 1),
                Dividend.ex_date <= date(year, 12, 31),
            )
        )
        year_divs = result.scalars().all()
        total = sum(Decimal(str(d.value)) for d in year_divs) if year_divs else Decimal("0")

        dy = None
        if price and price > 0 and total > 0:
            dy = (total / price * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        history.append({"year": year, "total_dividends": total, "dy_percent": dy})

    return history


# ──────────────────────────────────────────────────────────────────────────────
# Preço-teto (Método Barsi)
# ──────────────────────────────────────────────────────────────────────────────


async def calculate_barsi_ceiling(
    db: AsyncSession,
    ticker: str,
    desired_dy: Decimal,
    months: int = 12,
) -> Decimal | None:
    """Calcula o preço-teto pelo método Barsi.

    Preço-teto = média_dividendo_anual / (DY_desejado / 100)

    Onde média_dividendo_anual é calculada com base nos últimos `months` meses,
    anualizada se necessário.

    Retorna None se não houver histórico de dividendos suficiente.
    """
    if desired_dy <= 0:
        return None

    ticker = ticker.upper()
    cutoff = date.today() - timedelta(days=months * 30)

    result = await db.execute(
        select(Dividend).where(
            Dividend.ticker == ticker,
            Dividend.ex_date >= cutoff,
        )
    )
    dividends = result.scalars().all()

    if not dividends:
        return None

    total = sum(Decimal(str(d.value)) for d in dividends)

    # Anualiza
    if months != 12:
        annual_dividend = total * Decimal("12") / Decimal(str(months))
    else:
        annual_dividend = total

    ceiling = (annual_dividend / (desired_dy / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return ceiling


# ──────────────────────────────────────────────────────────────────────────────
# Identificação de oportunidades
# ──────────────────────────────────────────────────────────────────────────────


async def identify_opportunity(
    db: AsyncSession,
    ticker: str,
    desired_dy: Decimal = Decimal("6.0"),
) -> dict:
    """Avalia se o ativo está em uma zona de oportunidade de compra.

    Retorna dict com:
    - is_below_ceiling: bool — preço atual abaixo do preço-teto
    - ceiling_distance_pct: Decimal | None — % abaixo do teto (positivo = oportunidade)
    - current_dy: Decimal | None
    - barsi_ceiling: Decimal | None
    - current_price: Decimal | None
    """
    ticker = ticker.upper()

    price_result = await db.execute(
        select(MarketQuote.price).where(MarketQuote.ticker == ticker)
    )
    price_row = price_result.scalar_one_or_none()
    current_price = Decimal(str(price_row)) if price_row else None

    current_dy = await calculate_dy(db, ticker)
    barsi_ceiling = await calculate_barsi_ceiling(db, ticker, desired_dy)

    is_below_ceiling = False
    ceiling_distance_pct = None

    if current_price and barsi_ceiling and barsi_ceiling > 0:
        is_below_ceiling = current_price < barsi_ceiling
        ceiling_distance_pct = (
            (barsi_ceiling - current_price) / barsi_ceiling * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "ticker": ticker,
        "current_price": current_price,
        "barsi_ceiling": barsi_ceiling,
        "current_dy": current_dy,
        "desired_dy": desired_dy,
        "is_below_ceiling": is_below_ceiling,
        "ceiling_distance_pct": ceiling_distance_pct,
    }
