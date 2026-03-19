<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { usePortfolioStore } from '@/stores/portfolio'
import { useAuthStore } from '@/stores/auth'

// ── Tipos ──────────────────────────────────────────────────────────────────

interface DividendEvent {
  ticker: string
  asset_name: string | null
  value: number
  ex_date: string
  days_until_ex: number
  dividend_type: string
}

interface ProjectionReport {
  projected_monthly_income: number
  projected_annual_income: number
  avg_dy: number | null
}

interface PerformanceReport {
  total_invested: number
  current_value: number
  total_return_pct: number | null
}

interface KPIs {
  total_invested: number
  current_value: number
  return_pct: number | null
  monthly_income: number
  annual_income: number
  avg_dy: number | null
  upcoming_count: number
}

// ── Estado ─────────────────────────────────────────────────────────────────

const router = useRouter()
const portfolioStore = usePortfolioStore()
const auth = useAuthStore()

const kpis = ref<KPIs | null>(null)
const upcoming = ref<DividendEvent[]>([])
const loading = ref(true)

onMounted(async () => {
  await portfolioStore.fetchPortfolios()
  if (portfolioStore.portfolios.length === 0) {
    loading.value = false
    return
  }
  // Usa a primeira carteira para o dashboard de visão geral
  const pid = portfolioStore.portfolios[0].id
  await loadKPIs(pid)
})

async function loadKPIs(pid: number) {
  loading.value = true
  try {
    const [perfRes, projRes, calRes] = await Promise.allSettled([
      axios.get('/api/reports/performance', { params: { portfolio_id: pid } }),
      axios.get('/api/reports/projections', { params: { portfolio_id: pid } }),
      axios.get('/api/calendar/dividends', { params: { portfolio_id: pid, upcoming_days: 30 } }),
    ])

    const perf: PerformanceReport | null =
      perfRes.status === 'fulfilled' ? perfRes.value.data : null
    const proj: ProjectionReport | null =
      projRes.status === 'fulfilled' ? projRes.value.data : null
    const cal = calRes.status === 'fulfilled' ? calRes.value.data : null

    if (cal?.upcoming_events) {
      upcoming.value = cal.upcoming_events.slice(0, 5)
    }

    kpis.value = {
      total_invested: perf?.total_invested ?? 0,
      current_value: perf?.current_value ?? 0,
      return_pct: perf?.total_return_pct ?? null,
      monthly_income: proj?.projected_monthly_income ?? 0,
      annual_income: proj?.projected_annual_income ?? 0,
      avg_dy: proj?.avg_dy ?? null,
      upcoming_count: cal?.upcoming_events?.length ?? 0,
    }
  } finally {
    loading.value = false
  }
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmt(val: number, d = 2): string {
  return val.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })
}

function returnClass(val: number | null): string {
  if (val == null) return ''
  return val >= 0 ? 'positive' : 'negative'
}

function urgencyClass(days: number): string {
  if (days <= 7) return 'urgent'
  if (days <= 14) return 'soon'
  return ''
}

function fmtDate(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR')
}
</script>

<template>
  <div class="page-container">
    <div class="dash-header">
      <div>
        <h2>Dashboard</h2>
        <p class="coming-soon">Visão geral da sua primeira carteira.</p>
      </div>
      <router-link to="/carteiras" class="btn-link">Gerenciar Carteiras →</router-link>
    </div>

    <!-- Sem carteiras ───────────────────────────────────────────────────── -->
    <div v-if="!loading && portfolioStore.portfolios.length === 0" class="onboarding-card">
      <h3>Bem-vindo ao InvestControl!</h3>
      <p>Crie sua primeira carteira para começar a acompanhar seus investimentos.</p>
      <button class="btn-primary" @click="router.push('/carteiras')">
        Criar Carteira
      </button>
    </div>

    <div v-if="loading" class="loading-state">Carregando...</div>

    <template v-if="!loading && kpis && portfolioStore.portfolios.length > 0">
      <!-- KPIs ────────────────────────────────────────────────────────── -->
      <div class="kpi-grid">
        <div class="kpi-card accent-blue">
          <span class="kpi-icon">💰</span>
          <span class="kpi-label">Patrimônio atual</span>
          <span class="kpi-value">R$ {{ fmt(kpis.current_value) }}</span>
          <span class="kpi-sub">Investido: R$ {{ fmt(kpis.total_invested) }}</span>
        </div>

        <div class="kpi-card" :class="kpis.return_pct != null ? (kpis.return_pct >= 0 ? 'accent-green' : 'accent-red') : ''">
          <span class="kpi-icon">📈</span>
          <span class="kpi-label">Retorno total</span>
          <span class="kpi-value" :class="returnClass(kpis.return_pct)">
            {{ kpis.return_pct != null ? (kpis.return_pct >= 0 ? '+' : '') + fmt(kpis.return_pct) + '%' : '—' }}
          </span>
          <span class="kpi-sub">
            R$ {{ fmt(kpis.current_value - kpis.total_invested) }}
          </span>
        </div>

        <div class="kpi-card accent-green">
          <span class="kpi-icon">📅</span>
          <span class="kpi-label">Renda mensal projetada</span>
          <span class="kpi-value positive">R$ {{ fmt(kpis.monthly_income) }}</span>
          <span class="kpi-sub">R$ {{ fmt(kpis.annual_income) }} / ano</span>
        </div>

        <div class="kpi-card">
          <span class="kpi-icon">%</span>
          <span class="kpi-label">DY médio ponderado</span>
          <span class="kpi-value">{{ kpis.avg_dy != null ? fmt(kpis.avg_dy) + '%' : '—' }}</span>
          <span class="kpi-sub">{{ kpis.upcoming_count }} ex-dates nos próx. 30d</span>
        </div>
      </div>

      <!-- Próximos proventos ───────────────────────────────────────────── -->
      <div class="section-block">
        <div class="section-title-row">
          <h3 class="section-title">Próximos Ex-Dividendos</h3>
          <router-link to="/calendario" class="btn-link-sm">Ver calendário →</router-link>
        </div>

        <div v-if="upcoming.length === 0" class="empty-inline">
          Nenhum ex-date nos próximos 30 dias.
        </div>

        <div v-else class="upcoming-list">
          <div
            v-for="ev in upcoming"
            :key="ev.ticker + ev.ex_date"
            class="upcoming-item"
            :class="urgencyClass(ev.days_until_ex)"
          >
            <div class="upcoming-identity">
              <span class="upcoming-ticker">{{ ev.ticker }}</span>
              <span class="upcoming-name">{{ ev.asset_name }}</span>
            </div>
            <div class="upcoming-info">
              <span class="upcoming-date">{{ fmtDate(ev.ex_date) }}</span>
              <span class="upcoming-value">R$ {{ fmt(ev.value, 4) }}/cota</span>
            </div>
            <div class="upcoming-countdown" :class="urgencyClass(ev.days_until_ex)">
              <span class="days-num">{{ ev.days_until_ex }}</span>
              <span class="days-label">dias</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Atalhos rápidos ──────────────────────────────────────────────── -->
      <div class="shortcuts-grid">
        <router-link to="/aporte" class="shortcut-card">
          <span class="shortcut-icon">🎯</span>
          <span class="shortcut-label">Receber Recomendações de Aporte</span>
        </router-link>
        <router-link to="/alertas" class="shortcut-card">
          <span class="shortcut-icon">🔔</span>
          <span class="shortcut-label">Configurar Alertas</span>
        </router-link>
        <router-link to="/relatorios" class="shortcut-card">
          <span class="shortcut-icon">📊</span>
          <span class="shortcut-label">Ver Relatórios Completos</span>
        </router-link>
        <router-link to="/calendario" class="shortcut-card">
          <span class="shortcut-icon">🗓️</span>
          <span class="shortcut-label">Calendário de Proventos</span>
        </router-link>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dash-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.dash-header h2 { margin: 0 0 4px; }

.btn-link {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.1);
  color: #93c5fd;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn-link:hover { background: rgba(59, 130, 246, 0.2); }

.btn-primary {
  margin-top: 16px;
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary:hover { background: #1d4ed8; }

.loading-state { color: #64748b; padding: 24px 0; }

/* ── Onboarding ─────────────────────────────────────────────────────────── */

.onboarding-card {
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 20px;
  padding: 48px;
  text-align: center;
}

.onboarding-card h3 { margin: 0 0 8px; color: #93c5fd; font-size: 1.4rem; }
.onboarding-card p { color: #94a3b8; margin: 0; }

/* ── KPI Grid ───────────────────────────────────────────────────────────── */

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 28px;
}

.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 20px;
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 16px;
  transition: border-color 0.15s;
}

.kpi-card.accent-blue { border-color: rgba(59, 130, 246, 0.3); }
.kpi-card.accent-green { border-color: rgba(34, 197, 94, 0.25); }
.kpi-card.accent-red { border-color: rgba(239, 68, 68, 0.25); }

.kpi-icon { font-size: 1.3rem; margin-bottom: 4px; }
.kpi-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
.kpi-value { font-size: 1.5rem; font-weight: 800; color: #e5eefc; }
.kpi-sub { font-size: 0.78rem; color: #475569; }

.positive { color: #22c55e !important; }
.negative { color: #ef4444 !important; }

/* ── Próximos proventos ─────────────────────────────────────────────────── */

.section-block { margin-bottom: 28px; }

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title { margin: 0; font-size: 1rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }

.btn-link-sm { font-size: 0.82rem; color: #60a5fa; text-decoration: none; }
.btn-link-sm:hover { text-decoration: underline; }

.empty-inline { color: #475569; font-size: 0.875rem; padding: 12px 0; }

.upcoming-list { display: flex; flex-direction: column; gap: 8px; }

.upcoming-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 12px;
  flex-wrap: wrap;
}

.upcoming-item.urgent { border-color: rgba(239, 68, 68, 0.3); }
.upcoming-item.soon { border-color: rgba(245, 158, 11, 0.25); }

.upcoming-identity { display: flex; flex-direction: column; gap: 2px; min-width: 80px; }
.upcoming-ticker { font-size: 0.95rem; font-weight: 700; color: #93c5fd; }
.upcoming-name { font-size: 0.75rem; color: #64748b; }

.upcoming-info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.upcoming-date { font-size: 0.85rem; color: #cbd5e1; }
.upcoming-value { font-size: 0.78rem; color: #64748b; }

.upcoming-countdown {
  display: flex; flex-direction: column; align-items: center;
  padding: 6px 10px; border-radius: 8px;
  background: rgba(59, 130, 246, 0.1);
  min-width: 40px;
}

.upcoming-countdown.urgent { background: rgba(239, 68, 68, 0.12); }
.upcoming-countdown.soon { background: rgba(245, 158, 11, 0.1); }

.days-num { font-size: 1rem; font-weight: 800; color: #93c5fd; line-height: 1; }
.upcoming-countdown.urgent .days-num { color: #fca5a5; }
.upcoming-countdown.soon .days-num { color: #fcd34d; }
.days-label { font-size: 0.58rem; color: #64748b; text-transform: uppercase; }

/* ── Atalhos ────────────────────────────────────────────────────────────── */

.shortcuts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.shortcut-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 14px;
  text-decoration: none;
  transition: all 0.15s;
}

.shortcut-card:hover {
  border-color: rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.06);
  transform: translateY(-1px);
}

.shortcut-icon { font-size: 1.4rem; flex-shrink: 0; }
.shortcut-label { font-size: 0.85rem; color: #cbd5e1; font-weight: 500; }
</style>
