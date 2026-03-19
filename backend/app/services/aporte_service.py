"""Motor de Aporte Sob Demanda — FR1 do SRS InvestControl.

Recebe um valor disponível e uma carteira, e retorna uma lista ranqueada
de recomendações de compra com justificativas e limitações explicadas.

Algoritmo de score (0–100):
    Fator 1 — Distância ao preço-teto Barsi     (peso 35%)
    Fator 2 — DY atual vs. meta desejada        (peso 30%)
    Fator 3 — Sub-representação na carteira     (peso 20%)
    Fator 4 — Proximidade da data ex-dividendo  (peso 15%)

Cada fator é normalizado para 0–100 antes de aplicar o peso.
Ativos acima do preço-teto recebem penalidade de 20 pontos no score final.
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.dividend import Dividend
from app.db.models.market_data import MarketQuote
from app.db.models.portfolio import Portfolio
from app.db.models.portfolio_asset import PortfolioAsset
from app.schemas.aporte import AporteRecommendationOut, RecommendationItem
from app.services.rules_engine import (
    calculate_barsi_ceiling,
    calculate_dy,
    identify_opportunity,
)

# ──────────────────────────────────────────────────────────────────────────────
# Pesos do algoritmo de score
# ──────────────────────────────────────────────────────────────────────────────

_W_CEILING = Decimal("0.35")
_W_DY = Decimal("0.30")
_W_WEIGHT = Decimal("0.20")
_W_EX_DATE = Decimal("0.15")

_ABOVE_CEILING_PENALTY = Decimal("20")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────


def _clamp(value: Decimal, lo: Decimal = Decimal("0"), hi: Decimal = Decimal("100")) -> Decimal:
    return max(lo, min(hi, value))


def _next_ex_date(dividends: list[Dividend]) -> date | None:
    """Retorna a próxima data ex-dividendo futura, ou None."""
    today = date.today()
    future = [d.ex_date for d in dividends if d.ex_date >= today]
    return min(future) if future else None


def _score_ceiling_distance(ceiling_distance_pct: Decimal | None, is_below: bool) -> Decimal:
    """Score baseado na distância ao preço-teto.

    > 30% abaixo = 100 pts
    0% = 50 pts (exatamente no teto)
    Acima do teto = 0 pts
    """
    if ceiling_distance_pct is None:
        return Decimal("50")  # sem teto calculado → neutro
    if not is_below:
        return Decimal("0")
    # Normaliza: 0% → 50pts, 30%+ → 100pts
    raw = Decimal("50") + (ceiling_distance_pct / Decimal("30")) * Decimal("50")
    return _clamp(raw)


def _score_dy(current_dy: Decimal | None, desired_dy: Decimal) -> Decimal:
    """Score baseado no DY atual vs. DY desejado.

    DY = 2× o desejado = 100 pts
    DY = desejado      = 70 pts
    DY = 0             = 0 pts
    """
    if current_dy is None or current_dy <= 0:
        return Decimal("0")
    ratio = current_dy / desired_dy
    raw = ratio * Decimal("70")
    return _clamp(raw)


def _score_portfolio_weight(
    position_value: Decimal,
    total_portfolio_value: Decimal,
    asset_count: int,
) -> Decimal:
    """Score baseado na sub-representação do ativo na carteira.

    Peso ideal = 1 / n_ativos (carteira igualmente distribuída).
    Quanto mais abaixo do peso ideal, maior o score.
    """
    if total_portfolio_value <= 0 or asset_count == 0:
        return Decimal("50")  # neutro para carteira vazia

    ideal_weight = Decimal("1") / Decimal(str(asset_count))
    actual_weight = position_value / total_portfolio_value

    # Diferença: positivo = abaixo do peso ideal (oportunidade de rebalancear)
    gap = ideal_weight - actual_weight
    # Normaliza: gap = ideal_weight (zero no portfólio) = 100 pts
    raw = (gap / ideal_weight) * Decimal("100") if ideal_weight > 0 else Decimal("50")
    return _clamp(raw)


def _score_ex_date(next_ex: date | None) -> Decimal:
    """Score baseado na proximidade da próxima data ex-dividendo.

    ≤ 7 dias  = 100 pts
    ≤ 30 dias = 75 pts
    ≤ 60 dias = 40 pts
    > 60 dias / sem data = 10 pts
    """
    if next_ex is None:
        return Decimal("10")
    days_until = (next_ex - date.today()).days
    if days_until <= 7:
        return Decimal("100")
    if days_until <= 30:
        return Decimal("75")
    if days_until <= 60:
        return Decimal("40")
    return Decimal("10")


def _build_justifications(
    ceiling_distance_pct: Decimal | None,
    is_below_ceiling: bool,
    current_dy: Decimal | None,
    desired_dy: Decimal,
    next_ex: date | None,
    portfolio_weight_pct: Decimal | None,
    ideal_weight_pct: Decimal | None,
) -> tuple[list[str], list[str]]:
    """Monta as listas de justificativas e limitações para a recomendação."""
    justifications: list[str] = []
    limitations: list[str] = []

    # Fator 1 — preço-teto
    if ceiling_distance_pct is not None:
        if is_below_ceiling:
            justifications.append(
                f"Abaixo do preço-teto Barsi em {ceiling_distance_pct:.1f}%"
            )
        else:
            limitations.append(
                f"Acima do preço-teto Barsi em {abs(ceiling_distance_pct):.1f}%"
            )
    else:
        limitations.append("Preço-teto não calculável (histórico de dividendos insuficiente)")

    # Fator 2 — DY
    if current_dy is not None:
        if current_dy >= desired_dy:
            justifications.append(
                f"DY de {current_dy:.2f}% ≥ meta de {desired_dy:.1f}%"
            )
        else:
            limitations.append(
                f"DY de {current_dy:.2f}% abaixo da meta de {desired_dy:.1f}%"
            )
    else:
        limitations.append("DY não calculável (sem histórico de dividendos recentes)")

    # Fator 3 — peso na carteira
    if portfolio_weight_pct is not None and ideal_weight_pct is not None:
        if portfolio_weight_pct < ideal_weight_pct:
            justifications.append(
                f"Sub-representado na carteira ({portfolio_weight_pct:.1f}% vs. ideal {ideal_weight_pct:.1f}%)"
            )
        else:
            limitations.append(
                f"Já no peso alvo ({portfolio_weight_pct:.1f}% ≥ ideal {ideal_weight_pct:.1f}%)"
            )

    # Fator 4 — data ex
    if next_ex is not None:
        days_until = (next_ex - date.today()).days
        if days_until <= 30:
            justifications.append(
                f"Data ex-dividendo em {days_until} dias ({next_ex.strftime('%d/%m/%Y')})"
            )

    return justifications, limitations


# ──────────────────────────────────────────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────────────────────────────────────────


async def recommend_aporte(
    db: AsyncSession,
    portfolio: Portfolio,
    value: Decimal,
    desired_dy: Decimal,
    max_assets: int,
) -> AporteRecommendationOut:
    """Gera recomendações ranqueadas para o aporte.

    1. Carrega posições da carteira com dados do ativo.
    2. Para cada ativo, calcula os 4 fatores de score.
    3. Ordena por score decrescente.
    4. Calcula quantidade recomendada com base no valor disponível.
    5. Retorna as top `max_assets` recomendações com justificativas.
    """
    # ── Carrega carteira com posições ─────────────────────────────────────
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.positions).selectinload(PortfolioAsset.asset))
        .where(Portfolio.id == portfolio.id)
    )
    loaded = result.scalar_one()
    positions = loaded.positions

    if not positions:
        return AporteRecommendationOut(
            portfolio_id=portfolio.id,
            available_value=value,
            desired_dy=desired_dy,
            recommendations=[],
            remaining_value=value,
        )

    # ── Calcula valor total da carteira ───────────────────────────────────
    total_portfolio_value = Decimal("0")
    position_values: dict[int, Decimal] = {}

    for pos in positions:
        price_result = await db.execute(
            select(MarketQuote.price).where(MarketQuote.ticker == pos.asset.ticker)
        )
        price_row = price_result.scalar_one_or_none()
        current_price = Decimal(str(price_row)) if price_row else pos.avg_price

        pos_value = Decimal(str(pos.quantity)) * current_price
        position_values[pos.asset_id] = pos_value
        total_portfolio_value += pos_value

    n_assets = len([p for p in positions if p.quantity > 0])
    ideal_weight_pct = (Decimal("100") / Decimal(str(n_assets))) if n_assets > 0 else None

    # ── Calcula score para cada ativo ─────────────────────────────────────
    candidates: list[tuple[Decimal, PortfolioAsset, dict]] = []

    for pos in positions:
        ticker = pos.asset.ticker

        # Cotação atual
        price_result = await db.execute(
            select(MarketQuote.price).where(MarketQuote.ticker == ticker)
        )
        price_row = price_result.scalar_one_or_none()
        current_price = Decimal(str(price_row)) if price_row else None

        # Análise de oportunidade (teto + DY)
        opp = await identify_opportunity(db, ticker, desired_dy=desired_dy)
        ceiling_distance_pct: Decimal | None = opp["ceiling_distance_pct"]
        is_below_ceiling: bool = opp["is_below_ceiling"]
        current_dy: Decimal | None = opp["current_dy"]

        # Próxima data ex
        div_result = await db.execute(
            select(Dividend).where(
                Dividend.ticker == ticker,
                Dividend.ex_date >= date.today(),
            ).order_by(Dividend.ex_date)
        )
        upcoming_divs = list(div_result.scalars().all())
        next_ex = _next_ex_date(upcoming_divs)

        # Peso atual na carteira
        pos_value = position_values.get(pos.asset_id, Decimal("0"))
        portfolio_weight_pct = (
            (pos_value / total_portfolio_value * Decimal("100"))
            if total_portfolio_value > 0
            else None
        )

        # Scores individuais
        s_ceiling = _score_ceiling_distance(ceiling_distance_pct, is_below_ceiling)
        s_dy = _score_dy(current_dy, desired_dy)
        s_weight = _score_portfolio_weight(pos_value, total_portfolio_value, n_assets)
        s_ex = _score_ex_date(next_ex)

        # Score final ponderado
        score = (
            s_ceiling * _W_CEILING
            + s_dy * _W_DY
            + s_weight * _W_WEIGHT
            + s_ex * _W_EX_DATE
        )

        # Penalidade para ativos acima do teto
        if not is_below_ceiling and ceiling_distance_pct is not None:
            score = _clamp(score - _ABOVE_CEILING_PENALTY)

        score = score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        context = {
            "current_price": current_price,
            "barsi_ceiling": opp["barsi_ceiling"],
            "ceiling_distance_pct": ceiling_distance_pct,
            "is_below_ceiling": is_below_ceiling,
            "current_dy": current_dy,
            "next_ex": next_ex,
            "portfolio_weight_pct": portfolio_weight_pct,
            "ideal_weight_pct": ideal_weight_pct,
        }

        candidates.append((score, pos, context))

    # ── Ordena por score decrescente ──────────────────────────────────────
    candidates.sort(key=lambda x: x[0], reverse=True)

    # ── Monta recomendações ───────────────────────────────────────────────
    recommendations: list[RecommendationItem] = []
    remaining = value

    for score, pos, ctx in candidates[:max_assets]:
        current_price: Decimal | None = ctx["current_price"]

        # Quantidade recomendada: máximo que cabe no valor restante
        if current_price and current_price > 0 and remaining >= current_price:
            recommended_qty = int(remaining / current_price)
            total_cost = Decimal(str(recommended_qty)) * current_price
        else:
            recommended_qty = 0
            total_cost = Decimal("0")

        limitations: list[str]
        justifications: list[str]
        justifications, limitations = _build_justifications(
            ceiling_distance_pct=ctx["ceiling_distance_pct"],
            is_below_ceiling=ctx["is_below_ceiling"],
            current_dy=ctx["current_dy"],
            desired_dy=desired_dy,
            next_ex=ctx["next_ex"],
            portfolio_weight_pct=ctx["portfolio_weight_pct"],
            ideal_weight_pct=ctx["ideal_weight_pct"],
        )

        if recommended_qty == 0:
            limitations.append(
                f"Valor insuficiente para compra (preço: R$ {current_price:.2f})"
                if current_price
                else "Sem cotação disponível para calcular quantidade"
            )

        recommendations.append(
            RecommendationItem(
                ticker=pos.asset.ticker,
                asset_name=pos.asset.name,
                asset_type=pos.asset.asset_type,
                current_price=current_price,
                recommended_quantity=recommended_qty,
                total_cost=total_cost if recommended_qty > 0 else None,
                barsi_ceiling=ctx["barsi_ceiling"],
                ceiling_distance_pct=ctx["ceiling_distance_pct"],
                is_below_ceiling=ctx["is_below_ceiling"],
                current_dy=ctx["current_dy"],
                score=score,
                justifications=justifications,
                limitations=limitations,
            )
        )

        # Desconta o custo total do valor disponível para os próximos ativos
        if recommended_qty > 0:
            remaining -= total_cost

    return AporteRecommendationOut(
        portfolio_id=portfolio.id,
        available_value=value,
        desired_dy=desired_dy,
        recommendations=recommendations,
        remaining_value=remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    )
