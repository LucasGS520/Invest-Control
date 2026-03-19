<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { usePortfolioStore } from '@/stores/portfolio'

// ── Tipos ─────────────────────────────────────────────────────────────────

interface RecommendationItem {
  ticker: string
  asset_name: string
  asset_type: string
  current_price: number | null
  recommended_quantity: number
  total_cost: number | null
  barsi_ceiling: number | null
  ceiling_distance_pct: number | null
  is_below_ceiling: boolean
  current_dy: number | null
  score: number
  justifications: string[]
  limitations: string[]
}

interface AporteResult {
  portfolio_id: number
  available_value: number
  desired_dy: number
  recommendations: RecommendationItem[]
  remaining_value: number
}

// ── Estado ────────────────────────────────────────────────────────────────

const portfolioStore = usePortfolioStore()

const portfolioId = ref<number | ''>('')
const value = ref<number | ''>('')
const desiredDy = ref<number>(6.0)
const maxAssets = ref<number>(5)

const loading = ref(false)
const error = ref('')
const result = ref<AporteResult | null>(null)
const expandedTicker = ref<string | null>(null)

onMounted(async () => {
  await portfolioStore.fetchPortfolios()
  if (portfolioStore.portfolios.length > 0) {
    portfolioId.value = portfolioStore.portfolios[0].id
  }
})

// ── Computed ──────────────────────────────────────────────────────────────

const totalAllocated = computed(() => {
  if (!result.value) return 0
  return result.value.recommendations.reduce((sum, r) => sum + (r.total_cost ?? 0), 0)
})

const utilizationPct = computed(() => {
  if (!result.value || result.value.available_value === 0) return 0
  return Math.round((totalAllocated.value / result.value.available_value) * 100)
})

// ── Helpers ───────────────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 70) return '#22c55e'
  if (score >= 45) return '#f59e0b'
  return '#ef4444'
}

function scoreLabel(score: number): string {
  if (score >= 70) return 'Ótimo'
  if (score >= 45) return 'Regular'
  return 'Fraco'
}

function fmt(val: number | null | undefined, decimals = 2): string {
  if (val == null) return '—'
  return val.toLocaleString('pt-BR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function toggleExpand(ticker: string) {
  expandedTicker.value = expandedTicker.value === ticker ? null : ticker
}

// ── Ação principal ────────────────────────────────────────────────────────

async function handleRecommend() {
  error.value = ''
  result.value = null
  loading.value = true

  try {
    const { data } = await axios.post('/api/aporte/recommend', {
      portfolio_id: portfolioId.value,
      value: value.value,
      desired_dy: desiredDy.value,
      max_assets: maxAssets.value,
    })
    result.value = data
  } catch (err: unknown) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    error.value = axiosErr.response?.data?.detail || 'Erro ao gerar recomendações.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <h2>Aporte Sob Demanda</h2>
    <p class="coming-soon">Informe o valor disponível e receba recomendações ranqueadas de compra.</p>

    <!-- Formulário ─────────────────────────────────────────────────────── -->
    <form class="aporte-form" @submit.prevent="handleRecommend">
      <div class="form-row">
        <label class="form-field">
          Carteira
          <select v-model="portfolioId" required>
            <option value="" disabled>Selecione uma carteira</option>
            <option v-for="p in portfolioStore.portfolios" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>
          <span v-if="portfolioStore.portfolios.length === 0" class="hint">
            Nenhuma carteira encontrada. Crie uma em Carteiras.
          </span>
        </label>

        <label class="form-field">
          Valor disponível (R$)
          <input
            v-model.number="value"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="ex: 1000.00"
            required
          />
        </label>
      </div>

      <div class="form-row">
        <label class="form-field">
          DY desejado (%)
          <input v-model.number="desiredDy" type="number" min="0.1" step="0.1" />
          <span class="hint">Mínimo de Dividend Yield para cálculo do preço-teto Barsi</span>
        </label>

        <label class="form-field">
          Máx. de ativos na lista
          <input v-model.number="maxAssets" type="number" min="1" max="20" />
        </label>
      </div>

      <p v-if="error" class="form-error">{{ error }}</p>

      <button type="submit" :disabled="loading || portfolioId === ''">
        {{ loading ? 'Calculando...' : 'Gerar Recomendações' }}
      </button>
    </form>

    <!-- Resultado ──────────────────────────────────────────────────────── -->
    <template v-if="result">
      <!-- Resumo ─────────────────────────────────────────────────────── -->
      <div class="summary-row">
        <div class="summary-card">
          <span class="summary-label">Valor disponível</span>
          <span class="summary-value">R$ {{ fmt(result.available_value) }}</span>
        </div>
        <div class="summary-card">
          <span class="summary-label">Alocado</span>
          <span class="summary-value">R$ {{ fmt(totalAllocated) }}</span>
        </div>
        <div class="summary-card">
          <span class="summary-label">Utilização</span>
          <span class="summary-value">{{ utilizationPct }}%</span>
        </div>
        <div class="summary-card">
          <span class="summary-label">Saldo restante</span>
          <span class="summary-value">R$ {{ fmt(result.remaining_value) }}</span>
        </div>
      </div>

      <!-- Lista vazia ─────────────────────────────────────────────────── -->
      <div v-if="result.recommendations.length === 0" class="empty-state">
        Nenhum ativo encontrado nessa carteira. Registre posições em Carteiras para obter recomendações.
      </div>

      <!-- Cards de recomendação ────────────────────────────────────────── -->
      <div v-else class="recs-list">
        <article
          v-for="(rec, idx) in result.recommendations"
          :key="rec.ticker"
          class="rec-card"
          :class="{ expanded: expandedTicker === rec.ticker }"
        >
          <!-- Cabeçalho do card ────────────────────────────────────────── -->
          <div class="rec-header" @click="toggleExpand(rec.ticker)">
            <span class="rec-rank">#{{ idx + 1 }}</span>

            <div class="rec-identity">
              <span class="rec-ticker">{{ rec.ticker }}</span>
              <span class="rec-name">{{ rec.asset_name }}</span>
              <span class="rec-type-badge">{{ rec.asset_type }}</span>
            </div>

            <div class="rec-score-ring" :style="{ '--c': scoreColor(rec.score) }">
              <span class="rec-score-num">{{ fmt(rec.score, 0) }}</span>
              <span class="rec-score-label">{{ scoreLabel(rec.score) }}</span>
            </div>

            <div class="rec-summary">
              <div class="rec-summary-item">
                <span class="rec-label">Preço atual</span>
                <span class="rec-val">{{ rec.current_price != null ? `R$ ${fmt(rec.current_price)}` : '—' }}</span>
              </div>
              <div class="rec-summary-item">
                <span class="rec-label">Qtd. recomendada</span>
                <span class="rec-val qty" :class="{ zero: rec.recommended_quantity === 0 }">
                  {{ rec.recommended_quantity }}
                </span>
              </div>
              <div class="rec-summary-item">
                <span class="rec-label">Custo total</span>
                <span class="rec-val">{{ rec.total_cost != null ? `R$ ${fmt(rec.total_cost)}` : '—' }}</span>
              </div>
            </div>

            <span class="rec-toggle">{{ expandedTicker === rec.ticker ? '▲' : '▼' }}</span>
          </div>

          <!-- Detalhes expandidos ──────────────────────────────────────── -->
          <div v-if="expandedTicker === rec.ticker" class="rec-detail">
            <!-- Dados de mercado ──────────────────────────────────────── -->
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">Preço-teto Barsi</span>
                <span class="detail-val">
                  {{ rec.barsi_ceiling != null ? `R$ ${fmt(rec.barsi_ceiling)}` : '—' }}
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Distância ao teto</span>
                <span
                  class="detail-val"
                  :class="rec.ceiling_distance_pct != null ? (rec.is_below_ceiling ? 'positive' : 'negative') : ''"
                >
                  {{ rec.ceiling_distance_pct != null ? `${fmt(rec.ceiling_distance_pct, 1)}%` : '—' }}
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">DY atual</span>
                <span class="detail-val">{{ rec.current_dy != null ? `${fmt(rec.current_dy, 2)}%` : '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Score final</span>
                <span class="detail-val" :style="{ color: scoreColor(rec.score) }">{{ fmt(rec.score, 2) }} / 100</span>
              </div>
            </div>

            <!-- Justificativas ───────────────────────────────────────── -->
            <div v-if="rec.justifications.length > 0" class="tag-section">
              <h4>Pontos positivos</h4>
              <ul class="tag-list positive">
                <li v-for="j in rec.justifications" :key="j">{{ j }}</li>
              </ul>
            </div>

            <!-- Limitações ───────────────────────────────────────────── -->
            <div v-if="rec.limitations.length > 0" class="tag-section">
              <h4>Limitações</h4>
              <ul class="tag-list negative">
                <li v-for="l in rec.limitations" :key="l">{{ l }}</li>
              </ul>
            </div>
          </div>
        </article>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ── Formulário ─────────────────────────────────────────────────────────── */

.aporte-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 32px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 640px) {
  .form-row {
    grid-template-columns: 1fr;
  }
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.9rem;
  color: #cbd5e1;
}

.form-field input,
.form-field select {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.6);
  color: #e5eefc;
  outline: none;
  transition: border-color 0.15s;
}

.form-field input:focus,
.form-field select:focus {
  border-color: #3b82f6;
}

.hint {
  font-size: 0.78rem;
  color: #64748b;
}

.form-error {
  color: #f87171;
  font-size: 0.875rem;
  margin: 0;
}

.aporte-form button {
  align-self: flex-start;
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.aporte-form button:hover:not(:disabled) {
  background: #1d4ed8;
}

.aporte-form button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* ── Resumo ──────────────────────────────────────────────────────────────── */

.summary-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 20px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 14px;
}

.summary-label {
  font-size: 0.8rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.summary-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #e5eefc;
}

/* ── Lista de recomendações ──────────────────────────────────────────────── */

.empty-state {
  padding: 32px;
  text-align: center;
  color: #64748b;
  border: 1px dashed rgba(148, 163, 184, 0.2);
  border-radius: 16px;
}

.recs-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rec-card {
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  overflow: hidden;
  transition: border-color 0.15s;
}

.rec-card.expanded {
  border-color: rgba(59, 130, 246, 0.4);
}

/* ── Cabeçalho do card ───────────────────────────────────────────────────── */

.rec-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
  cursor: pointer;
  user-select: none;
}

.rec-header:hover {
  background: rgba(59, 130, 246, 0.06);
}

.rec-rank {
  font-size: 0.85rem;
  font-weight: 700;
  color: #475569;
  min-width: 28px;
}

.rec-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 110px;
}

.rec-ticker {
  font-size: 1.05rem;
  font-weight: 700;
  color: #93c5fd;
}

.rec-name {
  font-size: 0.8rem;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 130px;
}

.rec-type-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  width: fit-content;
}

/* Score ring ──────────────────────────────────────────────────────────── */

.rec-score-ring {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: 3px solid var(--c, #64748b);
  flex-shrink: 0;
}

.rec-score-num {
  font-size: 1rem;
  font-weight: 800;
  color: var(--c, #64748b);
  line-height: 1;
}

.rec-score-label {
  font-size: 0.58rem;
  color: #64748b;
  text-transform: uppercase;
}

/* Resumo numérico no cabeçalho ──────────────────────────────────────── */

.rec-summary {
  display: flex;
  gap: 20px;
  flex: 1;
  flex-wrap: wrap;
}

.rec-summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rec-label {
  font-size: 0.75rem;
  color: #64748b;
}

.rec-val {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e5eefc;
}

.rec-val.qty {
  color: #22c55e;
}

.rec-val.qty.zero {
  color: #ef4444;
}

.rec-toggle {
  font-size: 0.8rem;
  color: #475569;
  margin-left: auto;
}

/* ── Detalhes expandidos ─────────────────────────────────────────────────── */

.rec-detail {
  padding: 0 20px 20px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin: 16px 0;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  background: rgba(7, 17, 31, 0.5);
  border-radius: 10px;
}

.detail-label {
  font-size: 0.75rem;
  color: #64748b;
}

.detail-val {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e5eefc;
}

.detail-val.positive {
  color: #22c55e;
}

.detail-val.negative {
  color: #ef4444;
}

/* ── Tags de justificativas / limitações ─────────────────────────────────── */

.tag-section {
  margin-top: 12px;
}

.tag-section h4 {
  margin: 0 0 8px;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.tag-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-list li {
  font-size: 0.82rem;
  padding: 5px 12px;
  border-radius: 999px;
}

.tag-list.positive li {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #86efac;
}

.tag-list.negative li {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #fca5a5;
}
</style>
