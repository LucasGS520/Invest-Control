"""Endpoint de Aporte Sob Demanda — FR1 do SRS InvestControl.

POST /api/aporte/recommend
    Recebe valor disponível e preferências; retorna lista ranqueada de recomendações.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models.portfolio import Portfolio
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.aporte import AporteRecommendationOut, AporteRequest
from app.services.aporte_service import recommend_aporte

router = APIRouter(prefix="/aporte", tags=["Aporte"])


@router.post(
    "/recommend",
    response_model=AporteRecommendationOut,
    summary="Recomendações de Aporte Sob Demanda",
    status_code=status.HTTP_200_OK,
)
async def recommend(
    body: AporteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AporteRecommendationOut:
    """Gera recomendações ranqueadas de compra para o valor de aporte informado.

    - Verifica que a carteira pertence ao usuário autenticado.
    - Executa o motor de score com 4 fatores ponderados.
    - Retorna lista ordenada por score decrescente com justificativas e limitações.
    """
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == body.portfolio_id,
            Portfolio.user_id == current_user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carteira não encontrada ou não pertence ao usuário autenticado.",
        )

    return await recommend_aporte(
        db=db,
        portfolio=portfolio,
        value=body.value,
        desired_dy=body.desired_dy,
        max_assets=body.max_assets,
    )
