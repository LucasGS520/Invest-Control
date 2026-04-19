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

## Fluxo Oficial (implementado)

O alinhamento transaction-first foi concluído em 6 fases. O fluxo oficial é:

```
Carteira (nome + objetivo opcional)
  └─ Registrar transação → busca ticker → sistema resolve ativo automaticamente
       └─ Posição, preço médio e retorno calculados automaticamente
            └─ Dashboard: patrimônio, variação, proventos, Descobrir
```

**Contratos centrais:**
- `POST /portfolios/{id}/transactions` → `{ ticker, transaction_type, quantity, price, fees?, date }`
- `DELETE /portfolios/{id}/transactions/{tx_id}` → recalcula posição por replay
- `GET /market/search?q=` → busca ativo local com cotação do cache
- `GET /market/asset/{ticker}` → detalhe com contexto do usuário
- `GET /portfolios/{id}` → posições com `current_price`, `return_pct`, `change_percent`

**Pontos em aberto:**
- Ticker normalization para sufixos BR/US (`.SA` em yfinance/twelvedata)
- SLA de atualização por tipo de ativo
- Edição de transação com trilha de auditoria (atualmente: delete + recriar)
- Snapshot/materialização periódica de posição

---

### Resumo do Problema e Objetivo da Correção

- **Problema:** O núcleo transaction-first está funcional, porém há desalinhamento operacional na integração de mercado (normalização de ticker, observabilidade, governança de atualização e validação), gerando risco de inconsistência em cotações/proventos e impacto direto nas recomendações.

- **Sintoma observado:** Falhas intermitentes por provider, comportamento inconsistente para tickers BR/US, baixa visibilidade de cache/fallback/circuit breaker e critérios de qualidade ainda pouco “enforceáveis” em CI/produção.

- **Objetivo da correção:** Restaurar previsibilidade e qualidade do fluxo principal (carteira → transação → posição → recomendação), com dados de mercado confiáveis, monitoráveis e auditáveis.

- **Premissas:**
  - Fluxo transaction-first permanece como contrato de produto.
  - Endpoints removidos de calendário/relatórios não serão reintroduzidos nesta correção.
  - Sem mudança de regra de negócio principal de aporte, apenas estabilização de dados e execução.

---

### Riscos, Impacto e Decisões

- **Decisão Técnica Principal:** Criar uma camada canônica de normalização/resolução de ticker por provider, com observabilidade obrigatória no caminho de dados de mercado (cache, fallback, circuit breaker, latência e erro).

- **Risco Principal:** Alterar resolução de ticker sem validação gradual pode reduzir cobertura de ativos ou degradar acurácia temporariamente.

- **Impacto atual:** Recomendações, alertas e performance de carteira podem divergir por inconsistência de dados externos; operação fica reativa por falta de sinais claros de saúde.

- **Dependências:**
  - Variáveis de ambiente e credenciais dos providers.
  - Ordem de providers e timeouts configuráveis.
  - Tabelas de cache local (market_quotes e dividends).
  - Pipeline de testes e ambiente de homologação para validação controlada.

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
