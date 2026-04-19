# Guia de Operação — InvestControl

## Fluxos principais

### 1. Novo usuário → primeira transação

```
1. POST /auth/register            → obtém access_token
2. POST /portfolios/              → cria carteira com nome (mínimo)
3. POST /portfolios/{id}/transactions
   { ticker: "PETR4", type: "BUY", quantity: 100, price: "38.50", date: "2026-04-18" }
   → ativo criado automaticamente, posição calculada
4. GET /portfolios/{id}           → vê posição com preço atual (se cotação em cache)
```

### 2. Registrar transação com busca de ativo

No frontend (`/carteiras/:id` → aba Registrar):
1. Digitar ticker no campo de busca (mínimo 2 caracteres)
2. Aguardar sugestões via `GET /market/search?q=`
3. Clicar na sugestão → preenche ticker e preço atual automaticamente
4. Ajustar quantidade, tipo e data → Registrar

Via API diretamente: só enviar `ticker` no payload — o backend resolve o resto.

### 3. Corrigir uma transação errada

Não há edição de campos financeiros. O fluxo seguro é:
```
DELETE /portfolios/{id}/transactions/{tx_id}   → remove e recalcula posição
POST   /portfolios/{id}/transactions           → registra com valores corretos
```
A posição é recalculada por replay completo das transações restantes — sem risco de inconsistência.

### 4. Atualizar cotações manualmente

```
POST /market/quote/{ticker}/refresh   → força busca nos providers externos
```
O scheduler `update_quotes` já atualiza automaticamente a cada 15 minutos (configurável).

---

## Comportamento de fallback de mercado

### Cotação (`GET /market/quote/{ticker}`)

| Situação | Comportamento |
|---|---|
| Cache válido (< 15 min) | Retorna do banco local, sem chamar API externa |
| Cache expirado | Tenta `yfinance → twelvedata → brapi` em sequência |
| Provider com 3+ falhas recentes | Circuito aberto — provider ignorado por 60s |
| Todos os providers falharam | `502 Bad Gateway` com detalhe da falha |

### Enriquecimento de ativo (nome/setor/tipo)

| Situação | Comportamento |
|---|---|
| Ativo novo (ticker não existe no banco) | Criado com placeholder `name=ticker`, tipo inferido pelo sufixo |
| Enriquecimento bem-sucedido | `name`, `sector`, `asset_type` atualizados automaticamente |
| Enriquecimento falha (provider offline) | Placeholder mantido — transação NÃO é bloqueada |
| Re-tentativa | Próxima vez que `get_or_create_asset` for chamado com esse ticker e `name == ticker` |

### Dividendos

| Situação | Comportamento |
|---|---|
| Sincronização manual | `POST /market/dividends/{ticker}/sync` |
| Sincronização automática | Scheduler diário às 7h (antes da abertura do mercado) |
| Provider falha | Tenta `statusinvest → fundamentus → brapi` |
| Dividendo já registrado | Idempotente — não duplica pela `ex_date` |

---

## Erros comuns e soluções

### `400 Quantidade insuficiente`
```
{ "detail": "Quantidade insuficiente: disponível 70, solicitado 100." }
```
**Causa:** tentativa de SELL com mais cotas do que a posição atual.  
**Solução:** verificar posição atual em `GET /portfolios/{id}` e ajustar quantidade.

### `502 Falha ao obter cotação`
```
{ "detail": "Falha ao obter cotação para 'XPTO3': Ticker 'XPTO3' nao encontrado na brapi." }
```
**Causa:** ticker inválido ou providers indisponíveis.  
**Solução:** verificar se o ticker existe; aguardar reset do circuit breaker (60s); verificar conectividade.

### `404 Carteira não encontrada`
**Causa:** `portfolio_id` não pertence ao usuário autenticado ou não existe.

### `422 Unprocessable Entity`
**Causa:** validação do payload falhou (ex: `ticker` com menos de 4 caracteres, `price <= 0`).  
**Solução:** verificar formato em [api-contracts.md](api-contracts.md).

---

## Scheduler — tarefas automáticas

| Tarefa | Frequência | Função |
|---|---|---|
| Atualizar cotações | A cada 15 min (configurável) | `_update_all_quotes` — busca todos os ativos ativos |
| Sincronizar dividendos | Diariamente às 7h | `_sync_all_dividends` — atualiza proventos |
| Avaliar alertas | Após atualização de cotações | `evaluate_all_alerts` — dispara alertas configurados |

Configuração em `backend/app/tasks/update_quotes.py` e `backend/app/core/config.py`.

---

## Configurações de operação

```env
MARKET_DATA_CACHE_MINUTES=15         # TTL do cache de cotações
ASSET_METADATA_STALE_HOURS=24        # Validade de metadados de ativo
CIRCUIT_BREAKER_THRESHOLD=3          # Falhas para abrir o circuito
CIRCUIT_BREAKER_RESET_SECONDS=60.0   # Tempo até reset automático do circuito
MARKET_DATA_CONCURRENCY=5            # Chamadas externas simultâneas máximas
PRICE_PROVIDERS_ORDER=yfinance,twelvedata,brapi
DIVIDEND_PROVIDERS_ORDER=statusinvest,fundamentus,brapi
```

---

## Migrações de banco

Sempre rodar ao subir o ambiente ou após atualizar o código:
```bash
cd backend
alembic upgrade head
```

Para reverter a última migration:
```bash
alembic downgrade -1
```

Histórico de migrations em `backend/alembic/versions/`.
