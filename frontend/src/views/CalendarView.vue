<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { usePortfolioStore } from '@/stores/portfolio'

// ── Tipos ──────────────────────────────────────────────────────────────────

interface DividendEvent {
  ticker: string
  asset_name: string | null
  value: number
  ex_date: string
  payment_date: string | null
  dividend_type: string
  days_until_ex: number
}

interface CalendarData {
  portfolio_id: number
  upcoming_events: DividendEvent[]
  past_events: DividendEvent[]
}

// ── Estado ─────────────────────────────────────────────────────────────────

const portfolioStore = usePortfolioStore()
const portfolioId = ref<number | ''>('')
const data = ref<CalendarData | null>(null)
const loading = ref(false)
const error = ref('')
const activeTab = ref<'upcoming' | 'past'>('upcoming')

onMounted(async () => {
  await portfolioStore.fetchPortfolios()
  if (portfolioStore.portfolios.length > 0) {
    portfolioId.value = portfolioStore.portfolios[0].id
    await loadCalendar()
  }
})

// ── Grouped by month ────────────────────────────────────────────────────────

type MonthGroup = { label: string; events: DividendEvent[] }

function groupByMonth(events: DividendEvent[]): MonthGroup[] {
  const map = new Map<string, DividendEvent[]>()
  for (const ev of events) {
    const d = new Date(ev.ex_date + 'T00:00:00')
    const key = d.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(ev)
  }
  return Array.from(map.entries()).map(([label, evts]) => ({ label, events: evts }))
}

const upcomingGroups = computed(() => groupByMonth(data.value?.upcoming_events ?? []))
const pastGroups = computed(() => groupByMonth(data.value?.past_events ?? []))

const totalUpcomingValue = computed(() =>
  (data.value?.upcoming_events ?? []).reduce((s, e) => s + e.value, 0),
)

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmt(val: number, decimals = 4): string {
  return val.toLocaleString('pt-BR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function fmtDate(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR')
}

function urgencyClass(days: number): string {
  if (days <= 7) return 'urgent'
  if (days <= 30) return 'soon'
  return 'normal'
}

function typeColor(type: string): string {
  const map: Record<string, string> = {
    DIVIDENDO: '#22c55e',
    RENDIMENTO: '#3b82f6',
    JCP: '#f59e0b',
    AMORTIZACAO: '#a855f7',
  }
  return map[type] ?? '#64748b'
}

// ── Ações ───────────────────────────────────────────────────────────────────

async function loadCalendar() {
  if (!portfolioId.value) return
  loading.value = true
  error.value = ''
  data.value = null
  try {
    const { data: res } = await axios.get('/api/calendar/dividends', {
      params: { portfolio_id: portfolioId.value },
    })
    data.value = res
  } catch (err: unknown) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    error.value = axiosErr.response?.data?.detail || 'Erro ao carregar calendário.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <h2>Calendário de Proventos</h2>
    <p class="coming-soon">Acompanhe as datas ex-dividendo e pagamentos dos ativos da sua carteira.</p>

    <!-- Seletor de carteira ──────────────────────────────────────────────── -->
    <div class="toolbar">
      <label class="select-field">
        Carteira
        <select v-model="portfolioId" @change="loadCalendar">
          <option value="" disabled>Selecione</option>
          <option v-for="p in portfolioStore.portfolios" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
      </label>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>

    <div v-if="loading" class="loading-state">Carregando...</div>

    <template v-if="data && !loading">
      <!-- KPI — total próximos proventos ──────────────────────────────── -->
      <div v-if="data.upcoming_events.length > 0" class="kpi-row">
        <div class="kpi-card">
          <span class="kpi-label">Próximos proventos (por cota)</span>
          <span class="kpi-value">R$ {{ fmt(totalUpcomingValue) }}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Eventos futuros</span>
          <span class="kpi-value">{{ data.upcoming_events.length }}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Eventos passados (180d)</span>
          <span class="kpi-value">{{ data.past_events.length }}</span>
        </div>
      </div>

      <!-- Tabs ─────────────────────────────────────────────────────────── -->
      <div class="tabs">
        <button
          :class="['tab-btn', { active: activeTab === 'upcoming' }]"
          @click="activeTab = 'upcoming'"
        >
          Próximos ({{ data.upcoming_events.length }})
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'past' }]"
          @click="activeTab = 'past'"
        >
          Histórico ({{ data.past_events.length }})
        </button>
      </div>

      <!-- Lista vazia ────────────────────────────────────────────────── -->
      <div
        v-if="activeTab === 'upcoming' && data.upcoming_events.length === 0"
        class="empty-state"
      >
        Nenhum provento futuro encontrado nos próximos 90 dias.
        Sincronize dividendos em Mercado para obter dados atualizados.
      </div>
      <div
        v-if="activeTab === 'past' && data.past_events.length === 0"
        class="empty-state"
      >
        Nenhum provento encontrado nos últimos 180 dias.
      </div>

      <!-- Eventos futuros agrupados por mês ────────────────────────── -->
      <div v-if="activeTab === 'upcoming'">
        <div v-for="group in upcomingGroups" :key="group.label" class="month-group">
          <h3 class="month-label">{{ group.label }}</h3>
          <div class="events-list">
            <div
              v-for="ev in group.events"
              :key="ev.ticker + ev.ex_date"
              class="event-card"
              :class="urgencyClass(ev.days_until_ex)"
            >
              <div class="event-left">
                <span class="event-ticker">{{ ev.ticker }}</span>
                <span v-if="ev.asset_name" class="event-name">{{ ev.asset_name }}</span>
              </div>

              <div class="event-center">
                <span class="event-date">Ex: {{ fmtDate(ev.ex_date) }}</span>
                <span v-if="ev.payment_date" class="event-payment">
                  Pgto: {{ fmtDate(ev.payment_date) }}
                </span>
              </div>

              <div class="event-right">
                <span
                  class="event-type-badge"
                  :style="{ background: typeColor(ev.dividend_type) + '22', color: typeColor(ev.dividend_type), borderColor: typeColor(ev.dividend_type) + '55' }"
                >
                  {{ ev.dividend_type }}
                </span>
                <span class="event-value">R$ {{ fmt(ev.value) }}/cota</span>
              </div>

              <div class="event-countdown" :class="urgencyClass(ev.days_until_ex)">
                <span class="days-num">{{ ev.days_until_ex }}</span>
                <span class="days-label">dias</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Eventos passados agrupados por mês ───────────────────────── -->
      <div v-if="activeTab === 'past'">
        <div v-for="group in pastGroups" :key="group.label" class="month-group">
          <h3 class="month-label">{{ group.label }}</h3>
          <div class="events-list">
            <div
              v-for="ev in group.events"
              :key="ev.ticker + ev.ex_date"
              class="event-card past"
            >
              <div class="event-left">
                <span class="event-ticker">{{ ev.ticker }}</span>
                <span v-if="ev.asset_name" class="event-name">{{ ev.asset_name }}</span>
              </div>
              <div class="event-center">
                <span class="event-date">Ex: {{ fmtDate(ev.ex_date) }}</span>
                <span v-if="ev.payment_date" class="event-payment">
                  Pgto: {{ fmtDate(ev.payment_date) }}
                </span>
              </div>
              <div class="event-right">
                <span
                  class="event-type-badge"
                  :style="{ background: typeColor(ev.dividend_type) + '22', color: typeColor(ev.dividend_type), borderColor: typeColor(ev.dividend_type) + '55' }"
                >
                  {{ ev.dividend_type }}
                </span>
                <span class="event-value">R$ {{ fmt(ev.value) }}/cota</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
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

.form-error {
  color: #f87171;
  font-size: 0.875rem;
}

.loading-state {
  color: #64748b;
  padding: 32px 0;
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

/* ── Tabs ───────────────────────────────────────────────────────────────── */

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
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

/* ── Meses ──────────────────────────────────────────────────────────────── */

.month-group {
  margin-bottom: 28px;
}

.month-label {
  margin: 0 0 12px;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #475569;
  font-weight: 700;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ── Event card ─────────────────────────────────────────────────────────── */

.event-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 12px;
  flex-wrap: wrap;
}

.event-card.past {
  opacity: 0.65;
}

.event-card.urgent {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.05);
}

.event-card.soon {
  border-color: rgba(245, 158, 11, 0.3);
}

.event-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 90px;
}

.event-ticker {
  font-size: 1rem;
  font-weight: 700;
  color: #93c5fd;
}

.event-name {
  font-size: 0.78rem;
  color: #64748b;
}

.event-center {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 130px;
}

.event-date {
  font-size: 0.9rem;
  color: #cbd5e1;
}

.event-payment {
  font-size: 0.78rem;
  color: #64748b;
}

.event-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.event-type-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid;
}

.event-value {
  font-size: 0.9rem;
  font-weight: 600;
  color: #e5eefc;
}

.event-countdown {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 44px;
  padding: 6px 10px;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.12);
}

.event-countdown.urgent {
  background: rgba(239, 68, 68, 0.15);
}

.event-countdown.soon {
  background: rgba(245, 158, 11, 0.12);
}

.days-num {
  font-size: 1.05rem;
  font-weight: 800;
  color: #93c5fd;
  line-height: 1;
}

.event-countdown.urgent .days-num {
  color: #fca5a5;
}

.event-countdown.soon .days-num {
  color: #fcd34d;
}

.days-label {
  font-size: 0.6rem;
  color: #64748b;
  text-transform: uppercase;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: #64748b;
  border: 1px dashed rgba(148, 163, 184, 0.2);
  border-radius: 16px;
}
</style>
