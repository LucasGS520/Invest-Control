<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { usePortfolioStore } from '@/stores/portfolio'
import { useAuthStore } from '@/stores/auth'

// ── Tipos ──────────────────────────────────────────────────────────────────

interface KPIs {
  total_invested: number
  current_value: number
  return_pct: number | null
}

// ── Estado ─────────────────────────────────────────────────────────────────

const router = useRouter()
const portfolioStore = usePortfolioStore()
const auth = useAuthStore()

const kpis = ref<KPIs | null>(null)
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
    const { data } = await axios.get(`/api/portfolios/${pid}`)
    const positions: { current_value: number | null; avg_price: number; quantity: number }[] = data.positions ?? []
    const totalInvested = Number(data.total_invested ?? 0)
    const currentValue = positions.reduce(
      (sum, p) => sum + Number(p.current_value ?? p.avg_price * p.quantity),
      0,
    )
    const returnPct = totalInvested > 0 ? ((currentValue - totalInvested) / totalInvested) * 100 : null
    kpis.value = { total_invested: totalInvested, current_value: currentValue, return_pct: returnPct }
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

// ── Descobrir ────────────────────────────────────────────────────────────────

interface AssetSearchResult {
  ticker: string
  name: string
  sector: string | null
  asset_type: string
  price: number | null
  change_percent: number | null
}

interface AssetDetailOut {
  ticker: string
  name: string
  sector: string | null
  asset_type: string
  price: number | null
  change_percent: number | null
  volume: number | null
  positions: { portfolio_id: number; portfolio_name: string; quantity: number; avg_price: number; current_value: number | null; return_pct: number | null }[]
  total_dividends_received: number | null
}

const discoverQuery = ref('')
const discoverSuggestions = ref<AssetSearchResult[]>([])
const discoverLoading = ref(false)
const discoverDetail = ref<AssetDetailOut | null>(null)
let discoverTimer: ReturnType<typeof setTimeout> | null = null

function onDiscoverInput() {
  discoverDetail.value = null
  if (discoverTimer) clearTimeout(discoverTimer)
  if (discoverQuery.value.trim().length < 2) {
    discoverSuggestions.value = []
    return
  }
  discoverTimer = setTimeout(searchDiscover, 300)
}

async function searchDiscover() {
  discoverLoading.value = true
  try {
    const { data } = await axios.get('/api/market/search', { params: { q: discoverQuery.value.trim() } })
    discoverSuggestions.value = data
  } catch {
    discoverSuggestions.value = []
  } finally {
    discoverLoading.value = false
  }
}

async function loadAssetDetail(ticker: string) {
  discoverQuery.value = ticker
  discoverSuggestions.value = []
  try {
    const { data } = await axios.get(`/api/market/asset/${ticker}`)
    discoverDetail.value = data
  } catch {
    discoverDetail.value = null
  }
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
        <router-link to="/carteiras" class="shortcut-card">
          <span class="shortcut-icon">💼</span>
          <span class="shortcut-label">Gerenciar Carteiras</span>
        </router-link>
      </div>
    </template>

    <!-- ── Descobrir ──────────────────────────────────────────────────────── -->
    <div class="section-block discover-section">
      <h3 class="section-title">Descobrir Ativos</h3>
      <div class="discover-search-wrap">
        <input
          v-model="discoverQuery"
          type="text"
          class="discover-input"
          placeholder="Buscar por ticker ou nome (ex: PETR4, Petrobras)"
          autocomplete="off"
          @input="onDiscoverInput"
        />
        <div v-if="discoverSuggestions.length > 0" class="suggestions-list">
          <div
            v-for="s in discoverSuggestions"
            :key="s.ticker"
            class="suggestion-item"
            @click="loadAssetDetail(s.ticker)"
          >
            <span class="sug-ticker">{{ s.ticker }}</span>
            <span class="sug-name">{{ s.name }}</span>
            <span v-if="s.price" class="sug-price">R$ {{ fmt(s.price) }}</span>
          </div>
        </div>
        <div v-if="discoverLoading" class="search-hint">Buscando...</div>
      </div>

      <!-- Detalhe do ativo ────────────────────────────────────────────────── -->
      <div v-if="discoverDetail" class="asset-detail-card">
        <div class="asset-detail-header">
          <div>
            <span class="asset-detail-ticker">{{ discoverDetail.ticker }}</span>
            <span class="asset-detail-name">{{ discoverDetail.name }}</span>
            <span v-if="discoverDetail.sector" class="asset-detail-sector">{{ discoverDetail.sector }}</span>
          </div>
          <div class="asset-detail-price-block">
            <span class="asset-detail-price">{{ discoverDetail.price != null ? 'R$ ' + fmt(discoverDetail.price) : '—' }}</span>
            <span v-if="discoverDetail.change_percent != null" :class="discoverDetail.change_percent >= 0 ? 'positive' : 'negative'">
              {{ discoverDetail.change_percent >= 0 ? '+' : '' }}{{ fmt(discoverDetail.change_percent) }}%
            </span>
          </div>
        </div>

        <div v-if="discoverDetail.positions.length > 0" class="asset-detail-positions">
          <p class="positions-label">Você já possui este ativo:</p>
          <div v-for="p in discoverDetail.positions" :key="p.portfolio_id" class="position-row">
            <span class="pos-portfolio">{{ p.portfolio_name }}</span>
            <span class="pos-qty">{{ p.quantity }} cotas</span>
            <span class="pos-avg">PM R$ {{ fmt(p.avg_price) }}</span>
            <span v-if="p.return_pct != null" :class="p.return_pct >= 0 ? 'positive' : 'negative'">
              {{ p.return_pct >= 0 ? '+' : '' }}{{ fmt(p.return_pct) }}%
            </span>
          </div>
        </div>
        <p v-else class="no-position-hint">Você ainda não possui este ativo em nenhuma carteira.</p>

        <router-link to="/carteiras" class="btn-link-sm">Ir para Carteiras → Registrar Transação</router-link>
      </div>
    </div>
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

/* ── Descobrir ──────────────────────────────────────────────────────────── */

.discover-section { margin-top: 32px; }

.discover-search-wrap { position: relative; margin-bottom: 16px; }

.discover-input {
  width: 100%;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.6);
  color: #e5eefc;
  font-size: 0.95rem;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.discover-input:focus { border-color: #3b82f6; }

.suggestions-list {
  position: absolute;
  z-index: 100;
  top: 100%;
  left: 0;
  right: 0;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 10px;
  overflow: hidden;
  margin-top: 4px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.1s;
}

.suggestion-item:hover { background: rgba(59, 130, 246, 0.1); }

.sug-ticker { font-weight: 700; color: #93c5fd; min-width: 70px; }
.sug-name { flex: 1; font-size: 0.85rem; color: #94a3b8; }
.sug-price { font-size: 0.85rem; color: #e5eefc; }
.search-hint { font-size: 0.8rem; color: #64748b; padding: 6px 0; }

.asset-detail-card {
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.asset-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
}

.asset-detail-ticker { display: block; font-size: 1.3rem; font-weight: 800; color: #93c5fd; }
.asset-detail-name { display: block; font-size: 0.9rem; color: #e5eefc; }
.asset-detail-sector { display: block; font-size: 0.78rem; color: #64748b; margin-top: 2px; }

.asset-detail-price-block { text-align: right; }
.asset-detail-price { display: block; font-size: 1.5rem; font-weight: 700; color: #e5eefc; }

.asset-detail-positions { display: flex; flex-direction: column; gap: 8px; }
.positions-label { font-size: 0.8rem; color: #64748b; margin: 0 0 4px; }

.position-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.06);
  border-radius: 8px;
  font-size: 0.85rem;
}

.pos-portfolio { font-weight: 600; color: #cbd5e1; flex: 1; }
.pos-qty, .pos-avg { color: #94a3b8; }

.no-position-hint { font-size: 0.82rem; color: #64748b; margin: 0; }
.positive { color: #86efac; }
.negative { color: #fca5a5; }
</style>
