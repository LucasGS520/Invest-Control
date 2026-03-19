"""Base declarativa para todos os modelos SQLAlchemy."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Classe base que todos os modelos de banco de dados devem herdar."""

    pass
