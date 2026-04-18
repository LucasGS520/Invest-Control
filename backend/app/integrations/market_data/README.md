# Market Data Integrations

Esta pasta define o contrato interno da camada de integracao de dados de mercado.

## Objetivo

Unificar cotações, dividendos e dados estruturais vindos de providers externos sem mudar a API pública usada por `app/services/market_data_service.py`.

## Contratos

- `Quote`: representa cotação unificada com `ticker`, `price`, `change_percent`, `volume`, `timestamp` e `source`.
- `DividendItem`: representa provento unificado com `ticker`, `value`, `ex_date`, `payment_date`, `dividend_type` e `source`.
- `BasePriceProvider`: define `get_quote()` e fornece `get_quotes()` com fallback sequencial quando não houver batch nativo.
- `BaseDividendProvider`: define `get_dividends()`.

## Regras para providers

- Normalizar `ticker` para uppercase.
- Usar `Decimal` para valores monetários e percentuais.
- Preferir `datetime` timezone-aware em UTC para `timestamp`.
- Aplicar timeout curto por provider usando `settings.provider_timeouts_seconds`.
- Se houver suporte a batch, sobrescrever `get_quotes()` para reduzir latência.
- Não persistir no banco dentro do provider; persistência fica no agregador.

## Responsabilidades

- Provider: buscar e normalizar dados externos.
- Aggregator: escolher provider por prioridade, aplicar fallback e persistir em `MarketQuote` e `Dividend`.
- Service adapter: manter compatibilidade com as funções públicas existentes.
