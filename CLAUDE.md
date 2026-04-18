# Claude — Contexto e Instruções

## Sobre o Projeto *InvestControl*
O InvestControl é uma plataforma que se encaixa em um ambiente maior de gestão financeira pessoal, atuando como um sistema de apoio à decisão para investidores.
Ele se integra com fontes externas de dados de mercado para fornecer informações atualizadas e recomendações.
A arquitetura modular do sistema, com um backend robusto, permite que ele seja a base para futuras expansões e integrações com outras ferramentas financeiras, embora não execute ordens nem substitua consultoria financeira.

O projeto é separado por responsabilidades, em diferentes módulos:

**Backend**:

**Frontend**:


> Informações sobre a Stack e Tecnologias existentes em [STACK_INVEST.md](STACK_INVEST.md)

---

## Objetivo e Problemas a ser Resolvido

**Objetivo:** adicionar uma camada de integração/aggregaçao de fontes externas de dados de mercado dentro de `app/` para unificar cotações, dividendos e dados estruturais, usando as fontes escolhidas (yfinance, Twelve Data, StatusInvest, Fundamentus, B3), mantendo compatibilidade com a API já usada por `app/services/market_data_service.py` e por `app/tasks/update_quotes.py`.

- **Estratégia de Execução:** criar modelos unificados (Pydantic) para `Quote` e `DividendItem`; implementar providers concretos (yfinance, Twelve Data, StatusInvest, Fundamentus, B3); implementar agregador que:
  - tenta providers por ordem configurada;
  - usa fetch em lote quando disponível;
  - persiste resultados nos modelos existentes (`MarketQuote`, `Dividend`);
  - exporta mesma superfície que `market_data_service` (compatibilidade).

- **Premissas**
  - Banco PostgreSQL já disponível (como no projeto).
  - Scheduler continuará chamando `market_data_service.get_quote` e `sync_dividends` (assinaturas existentes).
  - A aplicação tem acesso à internet para consultar provedores.
  - Chaves de API (Twelve Data, B3 quando necessário) serão fornecidas via variáveis de ambiente.

---

## Análise de Riscos e Decisões Chave

**Decisões Técnicas Principais**
  - **Prioridade de fontes (configurável):** price → [yfinance, Twelve Data, brapi], dividends → [StatusInvest, Fundamentus, brapi]; B3 para dados estruturais/metadata. Ordem definida via `core.config`.
  - **Contrato unificado:** providers retornam objetos tipados (`Quote`, `DividendItem`) e agregador persiste em `MarketQuote`/`Dividend`.
  - **Compatibilidade:** manter `app/services/market_data_service.py` com mesmas funções públicas (`get_quote(db, ticker)`, `sync_dividends(db, ticker)`) — refatorado como adapter.
  - **Assincronia:** código principal em async; providers síncronos (yfinance) executam via `asyncio.to_thread`.
  - **Cache primário:** usar as tabelas já existentes como cache (evitar introduzir Redis inicialmente). Redis opcional como tarefa futura.
  - **Batch fetching:** onde disponível (Twelve Data, brapi, yfinance Tickers), usar chamadas em lote para eficiência na `update_quotes`.
  - **Rate limiting & backoff:** cada provider com timeout curto + retries exponenciais e circuit-breaker simples por provider.

- **Riscos Principais**
  - Scraping (StatusInvest/Fundamentus) fragiliza com mudanças de HTML.
  - Licenciamento/disponibilidade da B3.
  - Rate limits / bloqueios por provedores (yahoo/TwelveData).
  - Inconsistência de mapeamento de tickers entre fontes (BR vs. US suffixes).
  - Aumento de latência na `update_quotes` se não usar batch/concorrência controlada.

- **Dependências**
  - Runtime: `yfinance`, `pandas`, `twelvedata` (ou httpx), `beautifulsoup4`, `lxml`, `httpx` (já presente), opcional `aioredis` (cache).
  - Infra/ops: variáveis de ambiente para chaves (`TWELVEDATA_API_KEY`, possivelmente `B3_API_KEY`), internet outbound.

- **Impactos Arquiteturais**
  - Novo package `backend/app/integrations/market_data` — isolado da lógica de serviço.
  - Imagem Docker maior (pandas, lxml).
  - Latência de atualização aumenta sem batch; `tasks/update_quotes.py` deve usar batches e limite de concorrência.
  - Observabilidade requerida: logs e métricas por provider.

---

### Resultado Esperado

- Nova pasta `backend/app/integrations/market_data` com interfaces e providers, um `MarketDataAggregator` configurável (ordem de prioridade + fallback), adaptação mínima de `app/services/market_data_service.py` para delegar ao agregador sem mudar assinaturas públicas, testes e documentação atualizados.

---

## Regras e Instruções de Execução
**Regras obrigatórias de economia (NÃO IGNORAR)**
1) NÃO liste árvore inteira do projeto (evite `tree`, `ls -R`, etc.). Se precisar, liste apenas pastas-alvo da FASE.
2) NÃO leia arquivos completos. Leia no máximo 120 linhas por arquivo (ou trechos específicos). Se precisar de mais contextualização, peça antes.
3) Priorize busca (rg/grep) para localizar pontos de mudança antes de abrir arquivos.
5) Não cole conteúdo integral de arquivos na resposta. Mostre apenas:
   - arquivos alterados
   - resumo do diff (o que mudou e por quê)
   - comandos executados e resultados
6) Execute somente UMA FASE por vez. Ao terminar a FASE:
   - pare e peça autorização para a próxima FASE
7) Se detectar duplicação/overreach fora do escopo, interrompa e reporte.
