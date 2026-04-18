# InvestControl

## Visão geral
O repositório continha apenas o SRS do InvestControl. Como primeiro passo do desenvolvimento, foi criada a fundação técnica do MVP com a stack definida:

- **Backend:** FastAPI
- **Frontend:** Vue.js + Vite
- **Banco de dados:** PostgreSQL
- **Ambiente local:** Docker Compose

Essa estrutura inicial permite iniciar o desenvolvimento incremental dos requisitos funcionais descritos no SRS, principalmente:

- autenticação e segurança;
- gestão de carteiras, ativos e transações;
- aporte sob demanda;
- integração com dados de mercado.

## Estrutura criada

```text
backend/   API FastAPI e configuração inicial da aplicação
frontend/  Aplicação Vue.js com tela inicial do MVP
docker-compose.yml  Orquestra backend, frontend e PostgreSQL
```

## Decisões iniciais

1. **Monorepo simples** para manter backend e frontend versionados juntos no MVP.
2. **Endpoint de healthcheck** no backend para validar rapidamente ambiente, deploy e integrações futuras.
3. **Tela inicial orientada ao produto** no frontend para traduzir o SRS em módulos visíveis desde o começo.
4. **Variáveis de ambiente padronizadas** para facilitar evolução para autenticação, banco real e integrações externas.

## Próximos passos sugeridos

1. Implementar a modelagem inicial do domínio com usuários, carteiras, ativos e transações.
2. Configurar SQLAlchemy + Alembic no backend.
3. Definir contratos da API para autenticação e CRUD de carteira.
4. Conectar o frontend aos endpoints iniciais do backend.
5. Adicionar pipeline básico de testes e lint.

## Como subir o ambiente

```bash
docker compose up --build
```

Após iniciar os serviços:

- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`

## Observações

Esta entrega representa o **passo inicial** de construção do sistema, transformando o SRS em uma base executável e pronta para a próxima iteração.
## Integração de dados de mercado

O backend agora possui uma camada dedicada em `backend/app/integrations/market_data` para unificar cotações e proventos sem quebrar a API pública já usada pelo sistema.

- Cotações: prioridade configurável entre `yfinance`, `twelvedata` e `brapi`.
- Dividendos: prioridade configurável entre `statusinvest`, `fundamentus` e `brapi`.
- Persistência: dados continuam sendo gravados em `market_quotes` e `dividends`.
- Compatibilidade: `app/services/market_data_service.py` segue expondo as mesmas funções principais.
- Scheduler: `update_quotes` tenta caminho em lote antes do fallback unitário.

## Variáveis de ambiente de mercado

Exemplos das variáveis novas estão em `backend/.env.example`.

- `BRAPI_TOKEN`
- `TWELVEDATA_API_KEY`
- `TWELVEDATA_BASE_URL`
- `PRICE_PROVIDERS_ORDER`
- `DIVIDEND_PROVIDERS_ORDER`
- `MARKET_DATA_CONCURRENCY`
- `PROVIDER_TIMEOUTS_SECONDS`

## Limitações e pontos abertos

- `StatusInvest` e `Fundamentus` usam scraping HTML e podem exigir ajustes se a estrutura das páginas mudar.
- O provider da `B3` foi deixado como stub documentado, pois pode depender de licenciamento e credenciais.
- O cache principal segue baseado no banco relacional existente; cache distribuído permanece como melhoria futura.
