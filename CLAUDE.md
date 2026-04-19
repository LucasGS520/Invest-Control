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
- **Problema:** O sistema mantém módulos de Calendário e Relatórios que desviam do fluxo principal transaction-first e aumentam complexidade funcional/técnica sem aderência ao objetivo atual do produto.

- **Sintoma observado:** Há rotas, serviços, telas, navegação e testes dedicados a essas duas frentes, com acoplamento no dashboard e no bootstrap da API.

- **Objetivo da correção:** Remover completamente páginas, endpoints e componentes de Calendário e Relatórios, preservando estabilidade do fluxo principal (carteiras, transações, mercado e alertas).

- **Premissas:**
- O objetivo de produto validado é priorizar carteira + transações + posição + preço médio + desempenho.
- APIs consumidoras externas para calendário/relatórios não devem ser mantidas.
- O dashboard pode perder blocos não essenciais desde que permaneça funcional e sem erro.

---

### Riscos, Impacto e Decisões
- **Decisão Técnica Principal:** Remoção física do código (não apenas ocultar menu), com limpeza de imports e contratos para eliminar dívida técnica e evitar rotas órfãs.

- **Risco Principal:** Quebra de dashboard e navegação por dependência direta de chamadas para /api/reports e /api/calendar, causando erro em runtime se não houver desacoplamento simultâneo.

- **Impacto atual:** Complexidade desnecessária em backend, frontend e suíte de testes; manutenção dispersa fora do foco do produto.

- **Dependências:**
- Bootstrap de API em main.py, main.py, main.py, main.py.
- Rotas dedicadas em calendar.py e reports.py.
- Serviço/schema de relatórios em reports_service.py e reports.py.
- Schema de calendário em calendar.py.
- Frontend: roteador index.ts, index.ts, menu App.vue, dashboard DashboardView.vue.
- Testes dedicados: test_calendar.py e test_reports.py.

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
