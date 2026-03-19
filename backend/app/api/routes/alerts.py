"""Endpoints de Alertas Inteligentes (FR8).

GET    /api/alerts/        — lista alertas do usuário
POST   /api/alerts/        — cria alerta
GET    /api/alerts/{id}    — detalhe
PATCH  /api/alerts/{id}    — atualiza (ativa/desativa, muda threshold)
DELETE /api/alerts/{id}    — remove
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models.alert import Alert
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.alert import AlertCreate, AlertOut, AlertUpdate

router = APIRouter(prefix="/alerts", tags=["Alertas"])


def _check_owner(alert: Alert | None, user_id: int) -> Alert:
    if alert is None or alert.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta não encontrado.")
    return alert


@router.get("/", response_model=list[AlertOut], summary="Lista alertas do usuário")
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Alert]:
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == current_user.id)
        .order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/",
    response_model=AlertOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria novo alerta",
)
async def create_alert(
    body: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Alert:
    alert = Alert(
        user_id=current_user.id,
        ticker=body.ticker.upper(),
        alert_type=body.alert_type,
        threshold=float(body.threshold) if body.threshold is not None else None,
        days_before_ex=body.days_before_ex,
        is_active=True,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/{alert_id}", response_model=AlertOut, summary="Detalhe do alerta")
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    return _check_owner(result.scalar_one_or_none(), current_user.id)


@router.patch("/{alert_id}", response_model=AlertOut, summary="Atualiza alerta")
async def update_alert(
    alert_id: int,
    body: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = _check_owner(result.scalar_one_or_none(), current_user.id)

    if body.is_active is not None:
        alert.is_active = body.is_active
    if body.threshold is not None:
        alert.threshold = float(body.threshold)
    if body.days_before_ex is not None:
        alert.days_before_ex = body.days_before_ex

    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove alerta",
)
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = _check_owner(result.scalar_one_or_none(), current_user.id)
    await db.delete(alert)
    await db.commit()
