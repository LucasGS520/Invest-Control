"""Politica canonica de ticker: forma interna e mapeamento por provider.

Forma canonica: ticker limpo em maiusculas, sem sufixo de exchange (ex: PETR4, AAPL).
Cada provider recebe o ticker no formato que ele espera via resolve_for_provider().
"""

from __future__ import annotations

import re

# Ativos de bolsa brasileira: 4 letras + 1-2 digitos (acoes, FIIs, ETFs)
_BR_PATTERN = re.compile(r"^[A-Z]{4}\d{1,2}$")


def is_br_ticker(ticker: str) -> bool:
    """Retorna True se o ticker segue o padrao de ativos listados na B3."""
    return bool(_BR_PATTERN.match(ticker.upper().removesuffix(".SA")))


def to_canonical(raw_ticker: str) -> str:
    """Normaliza qualquer ticker para a forma canonica interna (sem sufixo de exchange)."""
    return raw_ticker.strip().upper().removesuffix(".SA")


def resolve_for_provider(canonical_ticker: str, provider: str) -> str:
    """Retorna o ticker no formato esperado pelo provider a partir da forma canonica.

    yfinance  : ativos BR recebem sufixo .SA (PETR4 -> PETR4.SA)
    brapi     : ticker limpo (remove .SA se presente)
    twelvedata: ticker limpo (TwelveData resolve a exchange internamente)
    demais    : ticker limpo
    """
    ticker = canonical_ticker.upper()
    if provider == "yfinance" and is_br_ticker(ticker):
        return f"{ticker}.SA"
    return ticker
