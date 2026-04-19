# InvestControl

Plataforma de apoio à decisão para investidores — fluxo centrado em transações, carteira simples e dados de mercado automáticos.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI + SQLAlchemy (async) + Alembic |
| Frontend | Vue 3 + Vite + Pinia |
| Banco | PostgreSQL |
| Ambiente local | Docker Compose |

> Detalhes em [STACK_INVEST.md](STACK_INVEST.md)

---

## Subir o ambiente

```bash
docker compose up --build
```

| Serviço | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Frontend | http://localhost:5173 |

---

## Fluxo principal

```
Usuário cria carteira (nome + objetivo opcional)
  └─ Registra transação (busca ticker → preenche qty/preço)
       └─ Sistema cria/enriquece ativo automaticamente via fontes externas
            └─ Posição e preço médio calculados automaticamente
                 └─ Dashboard exibe patrimônio, retorno e proventos
```

Não há cadastro manual de ativo. O usuário digita o ticker, o sistema resolve nome/setor/tipo via integração externa.

---

## Arquitetura do backend

```
app/
  api/routes/          Endpoints FastAPI
    portfolios.py      CRUD carteiras
    transactions.py    Registrar/remover transações (recalcula posição)
    assets.py          Legado — GET/POST de ativos
    market.py          Cotações, DY, preço-teto, busca, detalhe de ativo
  services/
    portfolio_service.py    apply_transaction, recalculate_position, get_portfolio_summary
    asset_service.py        get_or_create_asset, enrich_asset (enriquecimento automático)
    market_data_service.py  Adapter público para integração de mercado
    aporte_service.py       Recomendação de aporte
  integrations/market_data/
    aggregator.py      Orquestra fallback entre providers + circuit breaker
    base.py            Contratos: Quote, DividendItem, AssetInfo
    providers/         brapi, yfinance, twelvedata, statusinvest, fundamentus
  tasks/
    update_quotes.py   Scheduler APScheduler — atualiza cotações e dividendos
  db/models/           SQLAlchemy ORM
  alembic/versions/    Migrações incrementais
```

---

## Variáveis de ambiente relevantes

| Variável | Default | Descrição |
|---|---|---|
| `DATABASE_URL` | postgres local | Connection string PostgreSQL |
| `BRAPI_TOKEN` | `""` | Token brapi.dev (opcional) |
| `TWELVEDATA_API_KEY` | `""` | Chave Twelve Data (opcional) |
| `MARKET_DATA_CACHE_MINUTES` | `15` | TTL cache de cotações |
| `ASSET_METADATA_STALE_HOURS` | `24` | Validade de metadados de ativo |
| `CIRCUIT_BREAKER_THRESHOLD` | `3` | Falhas antes de abrir o circuito |
| `PRICE_PROVIDERS_ORDER` | `yfinance,twelvedata,brapi` | Ordem de fallback de cotações |

---

## Migrações

```bash
cd backend
alembic upgrade head
```

| Versão | Descrição |
|---|---|
| 0001 | Tabelas iniciais |
| 0002 | Dados de mercado |
| 0003 | Tabela de alertas |
| 0004 | `objective`/`currency` em portfolios; `fees` em transactions |

---

## Testes

```bash
cd backend
.venv/Scripts/python.exe -m pytest
```

Cobertura em: portfolios, transactions, aporte, market/aggregator, providers, alertas.
