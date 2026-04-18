"""Provider de dados estruturais da B3.

Implementado como stub seguro nesta fase porque a fonte oficial pode exigir
licenciamento, credenciais e/ou ingestao de arquivos fechados.
"""

from __future__ import annotations


class B3Provider:
    """Stub documentado para futura ingestao de dados estruturais oficiais."""

    provider_name = "b3"

    def __init__(self, *_args, **_kwargs) -> None:
        self.license_required = True

    async def get_quote(self, _ticker: str):
        raise NotImplementedError("B3Provider depende de licenca/credenciais antes de uso.")

    async def get_quotes(self, _tickers: list[str]):
        raise NotImplementedError("B3Provider depende de licenca/credenciais antes de uso.")

    async def get_structural_data(self, _ticker: str):
        raise NotImplementedError("B3Provider depende de licenca/credenciais antes de uso.")
