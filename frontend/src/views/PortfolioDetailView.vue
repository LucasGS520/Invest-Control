<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

// ── Tipos ──────────────────────────────────────────────────────────────────

interface PositionOut {
  id: number
  asset_id: number
  ticker: string
  asset_name: string
  asset_type: string
  quantity: number
  avg_price: number
  current_price: number | null
  current_value: number | null
  return_pct: number | null
  change_percent: number | null
}

interface PortfolioSummary {
  id: number
  name: string
  description: string | null
  objective: string | null
  currency: string
  created_at: string
  total_invested: number
  positions: PositionOut[]
}

interface TransactionOut {
  id: number
  asset_id: number
  ticker: string
  transaction_type: string
  quantity: number
  price: number
  fees: number | null
  date: string
  notes: string | null
}

interface AssetSearchResult {
  ticker: string
  name: string
  sector: string | null
  asset_type: string
  price: number | null
  change_percent: number | null
}

// ── Estado ─────────────────────────────────────────────────────────────────

const route = useRoute()
const portfolioId = Number(route.params.id)

const summary = ref<PortfolioSummary | null>(null)
const transactions = ref<TransactionOut[]>([])

const loading = ref(true)
const error = ref('')
const activeTab = ref<'positions' | 'transactions' | 'add'>('positions')

// Busca de ativo
const tickerQuery = ref('')
const suggestions = ref<AssetSearchResult[]>([])
const selectedAsset = ref<AssetSearchResult | null>(null)
const searchLoading = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

// Form nova transação
const txType = ref<'BUY' | 'SELL'>('BUY')
const txQty = ref<number | ''>('')
const txPrice = ref<number | ''>('')
const txFees = ref<number | ''>('')
const txDate = ref(new Date().toISOString().slice(0, 10))
const txNotes = ref('')
const txLoading = ref(false)
const txError = ref('')
const txSuccess = ref('')

onMounted(async () => {
  await Promise.all([loadSummary(), loadTransactions()])
})

// ── Computed ─────────────────────────────────────────────────────────────────

const activePositions = computed(() =>
  (summary.value?.positions ?? []).filter((p) => p.quantity > 0),
)

const totalCurrentValue = computed(() =>
  activePositions.value.reduce((sum, p) => sum + (p.current_value ?? p.quantity * p.avg_price), 0),
)

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmt(val: number, d = 2): string {
  return val.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })
}

function fmtDate(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR')
}

function retColor(val: number | null): string {
  if (val === null) return ''
  return val >= 0 ? 'positive' : 'negative'
}

// ── Ações ────────────────────────────────────────────────────────────────────

async function loadSummary() {
  try {
    const { data } = await axios.get(`/api/portfolios/${portfolioId}`)
    summary.value = data
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    error.value = e.response?.data?.detail || 'Erro ao carregar carteira.'
  } finally {
    loading.value = false
  }
}

async function loadTransactions() {
  try {
    const { data } = await axios.get(`/api/portfolios/${portfolioId}/transactions`)
    transactions.value = data
  } catch {
    // silently ignore
  }
}

function onTickerInput() {
  selectedAsset.value = null
  if (searchTimer) clearTimeout(searchTimer)
  if (tickerQuery.value.trim().length < 2) {
    suggestions.value = []
    return
  }
  searchTimer = setTimeout(searchAssets, 300)
}

async function searchAssets() {
  searchLoading.value = true
  try {
    const { data } = await axios.get('/api/market/search', { params: { q: tickerQuery.value.trim() } })
    suggestions.value = data
  } catch {
    suggestions.value = []
  } finally {
    searchLoading.value = false
  }
}

function selectAsset(asset: AssetSearchResult) {
  selectedAsset.value = asset
  tickerQuery.value = asset.ticker
  if (asset.price) txPrice.value = asset.price
  suggestions.value = []
}

function clearAsset() {
  selectedAsset.value = null
  tickerQuery.value = ''
  txPrice.value = ''
  suggestions.value = []
}

async function submitTransaction() {
  txError.value = ''
  txSuccess.value = ''
  const ticker = selectedAsset.value?.ticker || tickerQuery.value.trim().toUpperCase()
  if (!ticker || !txQty.value || !txPrice.value) {
    txError.value = 'Informe o ativo, quantidade e preço.'
    return
  }
  txLoading.value = true
  try {
    await axios.post(`/api/portfolios/${portfolioId}/transactions`, {
      ticker,
      transaction_type: txType.value,
      quantity: txQty.value,
      price: txPrice.value,
      fees: txFees.value || null,
      date: txDate.value,
      notes: txNotes.value || null,
    })
    txSuccess.value = 'Transação registrada!'
    txQty.value = ''
    txFees.value = ''
    txNotes.value = ''
    clearAsset()
    await Promise.all([loadSummary(), loadTransactions()])
    setTimeout(() => (txSuccess.value = ''), 3000)
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    txError.value = e.response?.data?.detail || 'Erro ao registrar transação.'
  } finally {
    txLoading.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <div v-if="loading" class="loading-state">Carregando...</div>
    <div v-if="error" class="form-error">{{ error }}</div>

    <template v-if="summary">
      <!-- Cabeçalho ─────────────────────────────────────────────────────── -->
      <div class="detail-header">
        <div>
          <h2>{{ summary.name }}</h2>
          <p v-if="summary.description" class="portfolio-desc">{{ summary.description }}</p>
          <p v-if="summary.objective" class="portfolio-objective">🎯 {{ summary.objective }}</p>
        </div>
        <div class="kpi-mini">
          <div class="kpi-mini-card">
            <span class="kpi-mini-label">Total investido</span>
            <span class="kpi-mini-value">R$ {{ fmt(summary.total_invested) }}</span>
          </div>
          <div class="kpi-mini-card">
            <span class="kpi-mini-label">Valor atual</span>
            <span class="kpi-mini-value">R$ {{ fmt(totalCurrentValue) }}</span>
          </div>
          <div class="kpi-mini-card">
            <span class="kpi-mini-label">Posições</span>
            <span class="kpi-mini-value">{{ activePositions.length }}</span>
          </div>
        </div>
      </div>

      <!-- Tabs ─────────────────────────────────────────────────────────── -->
      <div class="tabs">
        <button :class="['tab-btn', { active: activeTab === 'positions' }]" @click="activeTab = 'positions'">
          Posições ({{ activePositions.length }})
        </button>
        <button :class="['tab-btn', { active: activeTab === 'transactions' }]" @click="activeTab = 'transactions'">
          Transações ({{ transactions.length }})
        </button>
        <button :class="['tab-btn', { active: activeTab === 'add' }]" @click="activeTab = 'add'">
          + Registrar
        </button>
      </div>

      <!-- ── TAB: Posições ──────────────────────────────────────────── -->
      <div v-if="activeTab === 'positions'">
        <div v-if="activePositions.length === 0" class="empty-state">
          Nenhuma posição ativa. Registre uma compra na aba "Registrar".
        </div>
        <div v-else class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Ativo</th>
                <th>Tipo</th>
                <th class="num">Qtd</th>
                <th class="num">PM</th>
                <th class="num">Preço atual</th>
                <th class="num">Valor atual</th>
                <th class="num">Retorno</th>
                <th class="num">Var. dia</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pos in activePositions" :key="pos.id">
                <td>
                  <span class="ticker-cell">{{ pos.ticker }}</span>
                  <span class="name-cell">{{ pos.asset_name }}</span>
                </td>
                <td>
                  <span class="type-badge" :class="pos.asset_type.toLowerCase()">
                    {{ pos.asset_type }}
                  </span>
                </td>
                <td class="num">{{ pos.quantity }}</td>
                <td class="num">R$ {{ fmt(pos.avg_price) }}</td>
                <td class="num">{{ pos.current_price != null ? 'R$ ' + fmt(pos.current_price) : '—' }}</td>
                <td class="num">{{ pos.current_value != null ? 'R$ ' + fmt(pos.current_value) : '—' }}</td>
                <td class="num" :class="retColor(pos.return_pct)">
                  {{ pos.return_pct != null ? (pos.return_pct >= 0 ? '+' : '') + fmt(pos.return_pct) + '%' : '—' }}
                </td>
                <td class="num" :class="retColor(pos.change_percent)">
                  {{ pos.change_percent != null ? (pos.change_percent >= 0 ? '+' : '') + fmt(pos.change_percent) + '%' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── TAB: Transações ────────────────────────────────────────── -->
      <div v-if="activeTab === 'transactions'">
        <div v-if="transactions.length === 0" class="empty-state">
          Nenhuma transação registrada.
        </div>
        <div v-else class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Data</th>
                <th>Ativo</th>
                <th>Tipo</th>
                <th class="num">Qtd</th>
                <th class="num">Preço</th>
                <th class="num">Total</th>
                <th>Notas</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in transactions" :key="tx.id">
                <td>{{ fmtDate(tx.date) }}</td>
                <td class="ticker-cell">{{ tx.ticker }}</td>
                <td>
                  <span class="tx-badge" :class="tx.transaction_type.toLowerCase()">
                    {{ tx.transaction_type }}
                  </span>
                </td>
                <td class="num">{{ tx.quantity }}</td>
                <td class="num">R$ {{ fmt(tx.price) }}</td>
                <td class="num">R$ {{ fmt(tx.quantity * tx.price) }}</td>
                <td class="notes-cell">{{ tx.notes || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── TAB: Registrar ─────────────────────────────────────────── -->
      <div v-if="activeTab === 'add'" class="add-section">
        <div class="form-card">
          <h3>Registrar Transação</h3>

          <!-- Busca de ativo ─────────────────────────────────────────── -->
          <div class="ticker-search-wrap">
            <label class="form-field">
              Ativo (ticker ou nome)
              <div class="ticker-input-row">
                <input
                  v-model="tickerQuery"
                  type="text"
                  placeholder="ex: MXRF11 ou Maxi Renda"
                  maxlength="30"
                  autocomplete="off"
                  @input="onTickerInput"
                />
                <button v-if="tickerQuery" class="btn-clear" @click="clearAsset">✕</button>
              </div>
            </label>

            <!-- Sugestões ───────────────────────────────────────────── -->
            <div v-if="suggestions.length > 0" class="suggestions-list">
              <div
                v-for="s in suggestions"
                :key="s.ticker"
                class="suggestion-item"
                @click="selectAsset(s)"
              >
                <span class="sug-ticker">{{ s.ticker }}</span>
                <span class="sug-name">{{ s.name }}</span>
                <span v-if="s.price" class="sug-price">R$ {{ fmt(s.price) }}</span>
              </div>
            </div>
            <div v-if="searchLoading" class="search-hint">Buscando...</div>

            <!-- Preview do ativo selecionado ───────────────────────── -->
            <div v-if="selectedAsset" class="asset-preview">
              <span class="type-badge" :class="selectedAsset.asset_type.toLowerCase()">{{ selectedAsset.asset_type }}</span>
              <span class="preview-name">{{ selectedAsset.name }}</span>
              <span v-if="selectedAsset.sector" class="preview-sector">{{ selectedAsset.sector }}</span>
              <span v-if="selectedAsset.price" class="preview-price">
                R$ {{ fmt(selectedAsset.price) }}
                <span v-if="selectedAsset.change_percent" :class="retColor(selectedAsset.change_percent)">
                  ({{ selectedAsset.change_percent >= 0 ? '+' : '' }}{{ fmt(selectedAsset.change_percent) }}%)
                </span>
              </span>
            </div>
          </div>

          <div class="form-row-3">
            <label class="form-field">
              Tipo
              <select v-model="txType">
                <option value="BUY">Compra</option>
                <option value="SELL">Venda</option>
              </select>
            </label>
            <label class="form-field">
              Data
              <input v-model="txDate" type="date" />
            </label>
            <label class="form-field">
              Quantidade
              <input v-model.number="txQty" type="number" min="1" placeholder="ex: 100" />
            </label>
          </div>

          <div class="form-row">
            <label class="form-field">
              Preço unitário (R$)
              <input v-model.number="txPrice" type="number" min="0.0001" step="0.01" placeholder="ex: 10.50" />
            </label>
            <label class="form-field">
              Custos/taxas (R$, opcional)
              <input v-model.number="txFees" type="number" min="0" step="0.01" placeholder="ex: 0.50" />
            </label>
            <label class="form-field">
              Notas (opcional)
              <input v-model="txNotes" type="text" placeholder="Observação" />
            </label>
          </div>

          <p v-if="txError" class="form-error">{{ txError }}</p>
          <p v-if="txSuccess" class="form-success">{{ txSuccess }}</p>

          <button class="btn-primary" :disabled="txLoading" @click="submitTransaction">
            {{ txLoading ? 'Registrando...' : 'Registrar Transação' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.loading-state { color: #64748b; padding: 32px 0; }
.form-error { color: #f87171; font-size: 0.875rem; margin: 0 0 12px; }
.form-success { color: #86efac; font-size: 0.875rem; margin: 0 0 12px; }

/* ── Header ─────────────────────────────────────────────────────────────── */

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.detail-header h2 { margin: 0 0 4px; font-size: 1.75rem; }

.portfolio-desc {
  margin: 0;
  color: #94a3b8;
  font-size: 0.9rem;
}

.kpi-mini {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.kpi-mini-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 18px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 12px;
  min-width: 130px;
}

.kpi-mini-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
.kpi-mini-value { font-size: 1.1rem; font-weight: 700; color: #e5eefc; }

/* ── Tabs ───────────────────────────────────────────────────────────────── */

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.tab-btn {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.88rem;
  transition: all 0.15s;
}

.tab-btn:hover { background: rgba(59, 130, 246, 0.1); color: #93c5fd; }
.tab-btn.active { background: rgba(59, 130, 246, 0.18); border-color: rgba(59, 130, 246, 0.4); color: #93c5fd; font-weight: 600; }

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
}

.data-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }

.data-table th {
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.8);
  color: #64748b;
  font-size: 0.72rem;
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

.data-table tr:hover td { background: rgba(59, 130, 246, 0.04); }

.num { text-align: right; }

.ticker-cell { display: block; font-weight: 700; color: #93c5fd; }
.name-cell { display: block; font-size: 0.75rem; color: #64748b; }
.notes-cell { font-size: 0.8rem; color: #64748b; max-width: 180px; }

.type-badge {
  font-size: 0.7rem; font-weight: 700;
  padding: 2px 8px; border-radius: 999px;
}

.type-badge.fii { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.type-badge.acao { background: rgba(168, 85, 247, 0.15); color: #c084fc; }

.tx-badge {
  font-size: 0.7rem; font-weight: 700;
  padding: 2px 8px; border-radius: 999px;
}

.tx-badge.buy { background: rgba(34, 197, 94, 0.15); color: #86efac; }
.tx-badge.sell { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }

/* ── Seção de adicionar ─────────────────────────────────────────────────── */

.add-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.form-card {
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  padding: 24px;
}

.form-card h3 {
  margin: 0 0 16px;
  font-size: 1.05rem;
  color: #93c5fd;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

.form-row-3 {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

@media (max-width: 640px) {
  .form-row, .form-row-3 { grid-template-columns: 1fr; }
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.88rem;
  color: #cbd5e1;
}

.form-field input,
.form-field select {
  padding: 9px 13px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.6);
  color: #e5eefc;
  outline: none;
  transition: border-color 0.15s;
}

.form-field input:focus,
.form-field select:focus { border-color: #3b82f6; }

.btn-primary {
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }

.btn-secondary {
  padding: 10px 22px;
  border-radius: 10px;
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.1);
  color: #93c5fd;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.btn-secondary:hover:not(:disabled) { background: rgba(59, 130, 246, 0.2); }
.btn-secondary:disabled { opacity: 0.55; cursor: not-allowed; }

/* ── Retorno positivo/negativo ─────────────────────────────────────────── */
.positive { color: #86efac; }
.negative { color: #fca5a5; }

.portfolio-objective { margin: 2px 0 0; font-size: 0.82rem; color: #7dd3fc; }

/* ── Busca de ticker ────────────────────────────────────────────────────── */
.ticker-search-wrap { margin-bottom: 16px; position: relative; }

.ticker-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.ticker-input-row input { flex: 1; }

.btn-clear {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.btn-clear:hover { color: #f87171; border-color: rgba(248, 113, 113, 0.3); }

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

.asset-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(59, 130, 246, 0.07);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 10px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.preview-name { font-weight: 600; color: #e5eefc; }
.preview-sector { font-size: 0.8rem; color: #64748b; }
.preview-price { font-size: 0.9rem; color: #e5eefc; margin-left: auto; }
</style>
