<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { usePortfolioStore } from '@/stores/portfolio'

// ── Tipos ──────────────────────────────────────────────────────────────────

interface PositionPerf {
  ticker: string
  asset_name: string
  asset_type: string
  quantity: number
  avg_price: number
  current_price: number | null
  invested: number
  current_value: number | null
  return_value: number | null
  return_pct: number | null
}

interface PerformanceReport {
  portfolio_id: number
  portfolio_name: string
  total_invested: number
  current_value: number
  total_return: number
  total_return_pct: number | null
  positions: PositionPerf[]
}

interface MonthlyIncome {
  year: number
  month: number
  month_label: string
  total_value: number
}

interface DividendIncomeReport {
  portfolio_id: number
  monthly_income: MonthlyIncome[]
  total_12m: number
  avg_monthly_12m: number
}

interface PositionProjection {
  ticker: string
  asset_name: string
  quantity: number
  annual_income: number
  monthly_income: number
  dy: number | null
}

interface ProjectionReport {
  portfolio_id: number
  current_value: number
  projected_annual_income: number
  projected_monthly_income: number
  avg_dy: number | null
  positions: PositionProjection[]
}

// ── Estado ─────────────────────────────────────────────────────────────────

const portfolioStore = usePortfolioStore()
const portfolioId = ref<number | ''>('')
const activeTab = ref<'performance' | 'income' | 'projections'>('performance')

const perfReport = ref<PerformanceReport | null>(null)
const incomeReport = ref<DividendIncomeReport | null>(null)
const projReport = ref<ProjectionReport | null>(null)

const loading = ref(false)
const error = ref('')

onMounted(async () => {
  await portfolioStore.fetchPortfolios()
  if (portfolioStore.portfolios.length > 0) {
    portfolioId.value = portfolioStore.portfolios[0].id
    await loadAll()
  }
})

// ── Computed para gráfico de barras ─────────────────────────────────────────

const barChartData = computed(() => {
  if (!incomeReport.value) return []
  const months = [...incomeReport.value.monthly_income].reverse() // cronológico
  const max = Math.max(...months.map((m) => m.total_value), 0.01)
  return months.map((m) => ({
    label: m.month_label,
    value: m.total_value,
    heightPct: Math.round((m.total_value / max) * 100),
  }))
})

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmt(val: number | null | undefined, decimals = 2): string {
  if (val == null) return '—'
  return val.toLocaleString('pt-BR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function fmtPct(val: number | null | undefined): string {
  if (val == null) return '—'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${fmt(val)}%`
}

function returnClass(val: number | null | undefined): string {
  if (val == null) return ''
  return val >= 0 ? 'positive' : 'negative'
}

// ── Ações ───────────────────────────────────────────────────────────────────

async function loadAll() {
  if (!portfolioId.value) return
  loading.value = true
  error.value = ''
  try {
    const [p, i, pr] = await Promise.all([
      axios.get('/api/reports/performance', { params: { portfolio_id: portfolioId.value } }),
      axios.get('/api/reports/dividend-income', { params: { portfolio_id: portfolioId.value } }),
      axios.get('/api/reports/projections', { params: { portfolio_id: portfolioId.value } }),
    ])
    perfReport.value = p.data
    incomeReport.value = i.data
    projReport.value = pr.data
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    error.value = e.response?.data?.detail || 'Erro ao carregar relatórios.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <h2>Relatórios</h2>
    <p class="coming-soon">Performance, renda de dividendos e projeções de renda passiva.</p>

    <!-- Seletor + tabs ───────────────────────────────────────────────────── -->
    <div class="toolbar">
      <label class="select-field">
        Carteira
        <select v-model="portfolioId" @change="loadAll">
          <option value="" disabled>Selecione</option>
          <option v-for="p in portfolioStore.portfolios" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
      </label>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <div v-if="loading" class="loading-state">Carregando relatórios...</div>

    <template v-if="!loading && (perfReport || incomeReport || projReport)">
      <!-- Tabs ─────────────────────────────────────────────────────────── -->
      <div class="tabs">
        <button :class="['tab-btn', { active: activeTab === 'performance' }]" @click="activeTab = 'performance'">
          Performance
        </button>
        <button :class="['tab-btn', { active: activeTab === 'income' }]" @click="activeTab = 'income'">
          Renda de Dividendos
        </button>
        <button :class="['tab-btn', { active: activeTab === 'projections' }]" @click="activeTab = 'projections'">
          Projeções
        </button>
      </div>

      <!-- ── TAB PERFORMANCE ─────────────────────────────────────────── -->
      <div v-if="activeTab === 'performance' && perfReport">
        <!-- KPIs ──────────────────────────────────────────────────────── -->
        <div class="kpi-row">
          <div class="kpi-card">
            <span class="kpi-label">Total investido</span>
            <span class="kpi-value">R$ {{ fmt(perfReport.total_invested) }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Valor atual</span>
            <span class="kpi-value">R$ {{ fmt(perfReport.current_value) }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Retorno total</span>
            <span class="kpi-value" :class="returnClass(perfReport.total_return)">
              R$ {{ fmt(perfReport.total_return) }}
            </span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Retorno %</span>
            <span class="kpi-value" :class="returnClass(perfReport.total_return_pct)">
              {{ fmtPct(perfReport.total_return_pct) }}
            </span>
          </div>
        </div>

        <!-- Tabela de posições ─────────────────────────────────────────── -->
        <div v-if="perfReport.positions.length === 0" class="empty-state">
          Nenhuma posição ativa nesta carteira.
        </div>
        <div v-else class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Ativo</th>
                <th class="num">Qtd</th>
                <th class="num">PM</th>
                <th class="num">Cotação</th>
                <th class="num">Investido</th>
                <th class="num">Valor atual</th>
                <th class="num">Retorno</th>
                <th class="num">Ret. %</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pos in perfReport.positions" :key="pos.ticker">
                <td>
                  <span class="ticker-cell">{{ pos.ticker }}</span>
                  <span class="asset-name-cell">{{ pos.asset_name }}</span>
                </td>
                <td class="num">{{ pos.quantity }}</td>
                <td class="num">{{ fmt(pos.avg_price) }}</td>
                <td class="num">{{ pos.current_price != null ? fmt(pos.current_price) : '—' }}</td>
                <td class="num">{{ fmt(pos.invested) }}</td>
                <td class="num">{{ pos.current_value != null ? fmt(pos.current_value) : '—' }}</td>
                <td class="num" :class="returnClass(pos.return_value)">
                  {{ pos.return_value != null ? fmt(pos.return_value) : '—' }}
                </td>
                <td class="num" :class="returnClass(pos.return_pct)">
                  {{ fmtPct(pos.return_pct) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── TAB RENDA DE DIVIDENDOS ─────────────────────────────────── -->
      <div v-if="activeTab === 'income' && incomeReport">
        <!-- KPIs ──────────────────────────────────────────────────────── -->
        <div class="kpi-row">
          <div class="kpi-card">
            <span class="kpi-label">Total 12 meses</span>
            <span class="kpi-value">R$ {{ fmt(incomeReport.total_12m) }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Média mensal</span>
            <span class="kpi-value">R$ {{ fmt(incomeReport.avg_monthly_12m) }}</span>
          </div>
        </div>

        <!-- Gráfico de barras SVG ───────────────────────────────────────── -->
        <div class="chart-card">
          <h3 class="chart-title">Renda mensal por proventos (últimos 12 meses)</h3>
          <div v-if="barChartData.every((b) => b.value === 0)" class="empty-state">
            Nenhum provento registrado nos últimos 12 meses para os ativos desta carteira.
          </div>
          <div v-else class="bar-chart">
            <div
              v-for="bar in barChartData"
              :key="bar.label"
              class="bar-col"
            >
              <span class="bar-value">{{ bar.value > 0 ? `R$ ${fmt(bar.value, 0)}` : '' }}</span>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ height: bar.heightPct + '%' }"
                />
              </div>
              <span class="bar-label">{{ bar.label }}</span>
            </div>
          </div>
        </div>

        <!-- Tabela de renda mensal ─────────────────────────────────────── -->
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Mês</th>
                <th class="num">Renda estimada</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in incomeReport.monthly_income" :key="m.year + '-' + m.month">
                <td>{{ m.month_label }}</td>
                <td class="num" :class="m.total_value > 0 ? 'positive' : ''">
                  R$ {{ fmt(m.total_value) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── TAB PROJEÇÕES ───────────────────────────────────────────── -->
      <div v-if="activeTab === 'projections' && projReport">
        <!-- KPIs ──────────────────────────────────────────────────────── -->
        <div class="kpi-row">
          <div class="kpi-card">
            <span class="kpi-label">Valor da carteira</span>
            <span class="kpi-value">R$ {{ fmt(projReport.current_value) }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Renda anual projetada</span>
            <span class="kpi-value positive">R$ {{ fmt(projReport.projected_annual_income) }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Renda mensal projetada</span>
            <span class="kpi-value positive">R$ {{ fmt(projReport.projected_monthly_income) }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">DY médio ponderado</span>
            <span class="kpi-value">{{ projReport.avg_dy != null ? fmt(projReport.avg_dy) + '%' : '—' }}</span>
          </div>
        </div>

        <!-- Tabela por ativo ───────────────────────────────────────────── -->
        <div v-if="projReport.positions.length === 0" class="empty-state">
          Nenhuma posição ativa com histórico de dividendos.
        </div>
        <div v-else class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Ativo</th>
                <th class="num">Qtd</th>
                <th class="num">DY</th>
                <th class="num">Renda anual</th>
                <th class="num">Renda mensal</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pos in projReport.positions" :key="pos.ticker">
                <td>
                  <span class="ticker-cell">{{ pos.ticker }}</span>
                  <span class="asset-name-cell">{{ pos.asset_name }}</span>
                </td>
                <td class="num">{{ pos.quantity }}</td>
                <td class="num">{{ pos.dy != null ? fmt(pos.dy) + '%' : '—' }}</td>
                <td class="num positive">R$ {{ fmt(pos.annual_income) }}</td>
                <td class="num positive">R$ {{ fmt(pos.monthly_income) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.toolbar {
  margin-bottom: 20px;
}

.select-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.9rem;
  color: #cbd5e1;
  min-width: 200px;
}

.select-field select {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.6);
  color: #e5eefc;
  outline: none;
  transition: border-color 0.15s;
}

.select-field select:focus {
  border-color: #3b82f6;
}

.form-error { color: #f87171; font-size: 0.875rem; margin-bottom: 12px; }
.loading-state { color: #64748b; padding: 24px 0; }

/* ── Tabs ───────────────────────────────────────────────────────────────── */

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.tab-btn {
  padding: 8px 20px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.tab-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  color: #93c5fd;
}

.tab-btn.active {
  background: rgba(59, 130, 246, 0.18);
  border-color: rgba(59, 130, 246, 0.4);
  color: #93c5fd;
  font-weight: 600;
}

/* ── KPIs ───────────────────────────────────────────────────────────────── */

.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 20px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 14px;
}

.kpi-label {
  font-size: 0.78rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.kpi-value {
  font-size: 1.3rem;
  font-weight: 700;
  color: #e5eefc;
}

/* ── Cores de retorno ───────────────────────────────────────────────────── */

.positive { color: #22c55e !important; }
.negative { color: #ef4444 !important; }

/* ── Gráfico de barras ──────────────────────────────────────────────────── */

.chart-card {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 24px;
}

.chart-title {
  margin: 0 0 20px;
  font-size: 0.9rem;
  color: #64748b;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 160px;
  padding-bottom: 28px;
  position: relative;
}

.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: flex-end;
  gap: 4px;
}

.bar-value {
  font-size: 0.6rem;
  color: #64748b;
  white-space: nowrap;
  text-align: center;
  min-height: 14px;
}

.bar-track {
  width: 100%;
  flex: 1;
  display: flex;
  align-items: flex-end;
  background: rgba(148, 163, 184, 0.06);
  border-radius: 4px 4px 0 0;
}

.bar-fill {
  width: 100%;
  background: linear-gradient(to top, #2563eb, #3b82f6);
  border-radius: 4px 4px 0 0;
  min-height: 2px;
  transition: height 0.3s ease;
}

.bar-label {
  font-size: 0.65rem;
  color: #64748b;
  text-align: center;
  white-space: nowrap;
  position: absolute;
  bottom: 0;
}

/* ── Tabelas ────────────────────────────────────────────────────────────── */

.empty-state {
  padding: 32px;
  text-align: center;
  color: #64748b;
  border: 1px dashed rgba(148, 163, 184, 0.2);
  border-radius: 16px;
}

.table-wrapper {
  overflow-x: auto;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  margin-bottom: 24px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th {
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.8);
  color: #64748b;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 700;
  white-space: nowrap;
}

.data-table td {
  padding: 12px 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
  color: #cbd5e1;
}

.data-table tr:hover td {
  background: rgba(59, 130, 246, 0.04);
}

.num {
  text-align: right;
}

.ticker-cell {
  display: block;
  font-weight: 700;
  color: #93c5fd;
}

.asset-name-cell {
  display: block;
  font-size: 0.75rem;
  color: #64748b;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
