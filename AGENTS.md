# Agentes de IA — Contexto e Instruções

## Sobre o Projeto *InvestControl*

Plataforma de apoio à decisão para investidores. Fluxo centrado em transações: o usuário cria uma carteira simples, registra compras/vendas buscando o ativo por ticker, e o sistema calcula automaticamente posição, preço médio e desempenho com dados de mercado de fontes externas.

> Detalhes da stack em [STACK_INVEST.md](STACK_INVEST.md)

---

## Arquitetura atual (pós-alinhamento)

### Backend

**Fluxo de transação:**
1. `POST /portfolios/{id}/transactions` recebe `{ ticker, transaction_type, quantity, price, fees?, date }`
2. `asset_service.get_or_create_asset(db, ticker)` cria o ativo se não existir e tenta enriquecê-lo via `MarketDataAggregator.get_asset_info`
3. `portfolio_service.apply_transaction` registra a `Transaction` e atualiza `PortfolioAsset` (preço médio ponderado)
4. `DELETE /portfolios/{id}/transactions/{tx_id}` remove e chama `recalculate_position` (replay completo)

**Integração de mercado:**
- `MarketDataAggregator` orquestra fallback entre providers com `_CircuitBreaker` (abre após 3 falhas, reseta em 60s)
- Ordem de cotação: `yfinance → twelvedata → brapi`
- Ordem de dividendos: `statusinvest → fundamentus → brapi`
- Enriquecimento de ativo (`AssetInfo`): `yfinance` e `brapi` implementam `BaseAssetInfoProvider`
- Cache de cotações: TTL configurável (`MARKET_DATA_CACHE_MINUTES`, padrão 15 min)
- Enriquecimento de metadados: disparado quando `asset.name == asset.ticker` (placeholder)

**APIs orientadas ao produto:**
- `GET /market/search?q=` — busca ativo por ticker/nome no banco local
- `GET /market/asset/{ticker}` — detalhe: cotação + posição do usuário + dividendos
- `GET /portfolios/{id}` — resumo com posições enriquecidas (current_price, return_pct, change_percent)

### Frontend

**Macroáreas:**
1. **Carteira** (`/carteiras`, `/carteiras/:id`) — visão de posições com retorno em tempo real, fluxo de transação via busca de ticker
2. **Dashboard/Descobrir** (`/dashboard`) — KPIs da carteira principal + seção Descobrir com busca de ativo e detalhe
3. **Demais rotas** — relatórios, aporte, calendário, alertas (mantidos)

**Fluxo de transação no frontend:**
- Usuário digita ticker no input → debounce → `GET /market/search?q=` → dropdown de sugestões
- Seleciona ativo → preview com nome/setor/cotação preenche automaticamente o preço
- Preenche qty, tipo, data → `POST /portfolios/{id}/transactions` com `ticker`

---

## Decisões técnicas registradas

| Decisão | Motivo |
|---|---|
| `ticker` em vez de `asset_id` na criação de transação | Remove obrigatoriedade de cadastro prévio de ativo |
| Enriquecimento fail-safe (try/except silencioso) | Falha de provider não bloqueia registro de transação |
| `recalculate_position` por replay | Garante consistência após deleção de transação |
| Circuit breaker por provider | Evita cascata de timeouts em providers instáveis |
| `name == ticker` como indicador de placeholder | Simples e sem coluna extra; re-enriquece quando necessário |

---

## Pontos em aberto

- Estratégia final de ticker normalization (sufixos BR `.SA` para yfinance/twelvedata)
- SLA de atualização de cotações por tipo de ativo (ação vs. FII vs. ETF)
- Edição de transação com recálculo auditável (soft edit vs. delete+create)
- Snapshot/materialização periódica de posição vs. cálculo sob demanda

---

## Regras obrigatórias de economia (NÃO IGNORAR)

1. NÃO liste árvore inteira do projeto (`tree`, `ls -R`, etc.)
2. NÃO leia arquivos completos. Máximo 120 linhas por vez
3. Priorize busca (`rg`/`grep`) para localizar pontos de mudança antes de abrir arquivos
4. Não cole conteúdo integral de arquivos na resposta
5. Execute apenas UMA FASE por vez; pare e peça autorização para a próxima
6. Se detectar duplicação/overreach fora do escopo, interrompa e reporte
