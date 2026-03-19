<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

// ── Tipos ──────────────────────────────────────────────────────────────────

type AlertType = 'PRICE_BELOW' | 'PRICE_ABOVE' | 'BELOW_CEILING' | 'EX_DATE'

interface AlertItem {
  id: number
  ticker: string
  alert_type: AlertType
  threshold: number | null
  days_before_ex: number | null
  is_active: boolean
  triggered_at: string | null
  created_at: string
}

// ── Estado ─────────────────────────────────────────────────────────────────

const alerts = ref<AlertItem[]>([])
const loading = ref(false)
const error = ref('')

// Form de criação
const showForm = ref(false)
const newTicker = ref('')
const newType = ref<AlertType>('PRICE_BELOW')
const newThreshold = ref<number | ''>('')
const newDays = ref<number>(7)
const formError = ref('')
const formLoading = ref(false)

onMounted(loadAlerts)

// ── Helpers ─────────────────────────────────────────────────────────────────

const TYPE_LABELS: Record<AlertType, string> = {
  PRICE_BELOW: 'Preço abaixo de',
  PRICE_ABOVE: 'Preço acima de',
  BELOW_CEILING: 'Abaixo do teto Barsi',
  EX_DATE: 'Data ex-dividendo em',
}

const TYPE_DESCRIPTIONS: Record<AlertType, string> = {
  PRICE_BELOW: 'Dispara quando o preço cai abaixo do valor definido.',
  PRICE_ABOVE: 'Dispara quando o preço sobe acima do valor definido.',
  BELOW_CEILING: 'Dispara quando o ativo está abaixo do preço-teto Barsi calculado.',
  EX_DATE: 'Dispara N dias antes da próxima data ex-dividendo.',
}

function needsThreshold(type: AlertType): boolean {
  return type === 'PRICE_BELOW' || type === 'PRICE_ABOVE'
}

function needsDays(type: AlertType): boolean {
  return type === 'EX_DATE'
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function alertDescription(a: AlertItem): string {
  if (a.alert_type === 'PRICE_BELOW') return `Preço ≤ R$ ${a.threshold?.toFixed(2)}`
  if (a.alert_type === 'PRICE_ABOVE') return `Preço ≥ R$ ${a.threshold?.toFixed(2)}`
  if (a.alert_type === 'BELOW_CEILING') return 'Abaixo do preço-teto Barsi'
  if (a.alert_type === 'EX_DATE') return `Ex-date em ≤ ${a.days_before_ex} dias`
  return a.alert_type
}

function statusClass(a: AlertItem): string {
  if (!a.is_active) return 'inactive'
  if (a.triggered_at) return 'triggered'
  return 'active'
}

// ── Ações ───────────────────────────────────────────────────────────────────

async function loadAlerts() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/alerts/')
    alerts.value = data
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    error.value = e.response?.data?.detail || 'Erro ao carregar alertas.'
  } finally {
    loading.value = false
  }
}

async function createAlert() {
  formError.value = ''
  if (!newTicker.value.trim()) {
    formError.value = 'Informe o ticker do ativo.'
    return
  }
  if (needsThreshold(newType.value) && !newThreshold.value) {
    formError.value = 'Informe o valor de referência.'
    return
  }

  formLoading.value = true
  try {
    await axios.post('/api/alerts/', {
      ticker: newTicker.value.toUpperCase().trim(),
      alert_type: newType.value,
      threshold: needsThreshold(newType.value) ? newThreshold.value : undefined,
      days_before_ex: needsDays(newType.value) ? newDays.value : undefined,
    })
    newTicker.value = ''
    newThreshold.value = ''
    newDays.value = 7
    showForm.value = false
    await loadAlerts()
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    formError.value = e.response?.data?.detail || 'Erro ao criar alerta.'
  } finally {
    formLoading.value = false
  }
}

async function toggleAlert(a: AlertItem) {
  try {
    await axios.patch(`/api/alerts/${a.id}`, { is_active: !a.is_active })
    a.is_active = !a.is_active
  } catch {
    // silently ignore
  }
}

async function deleteAlert(id: number) {
  try {
    await axios.delete(`/api/alerts/${id}`)
    alerts.value = alerts.value.filter((a) => a.id !== id)
  } catch {
    // silently ignore
  }
}
</script>

<template>
  <div class="page-container">
    <h2>Alertas Inteligentes</h2>
    <p class="coming-soon">
      Configure alertas para ser notificado quando ativos atingirem condições de interesse.
    </p>

    <!-- Barra de ações ─────────────────────────────────────────────────── -->
    <div class="action-bar">
      <button class="btn-primary" @click="showForm = !showForm">
        {{ showForm ? 'Cancelar' : '+ Novo Alerta' }}
      </button>
    </div>

    <!-- Formulário de criação ──────────────────────────────────────────── -->
    <div v-if="showForm" class="form-card">
      <h3>Novo Alerta</h3>

      <div class="form-row">
        <label class="form-field">
          Ticker
          <input
            v-model="newTicker"
            type="text"
            placeholder="ex: MXRF11"
            maxlength="20"
          />
        </label>

        <label class="form-field">
          Tipo de alerta
          <select v-model="newType">
            <option value="PRICE_BELOW">Preço abaixo de</option>
            <option value="PRICE_ABOVE">Preço acima de</option>
            <option value="BELOW_CEILING">Abaixo do teto Barsi</option>
            <option value="EX_DATE">Data ex-dividendo</option>
          </select>
        </label>
      </div>

      <p class="type-description">{{ TYPE_DESCRIPTIONS[newType] }}</p>

      <div class="form-row" v-if="needsThreshold(newType) || needsDays(newType)">
        <label v-if="needsThreshold(newType)" class="form-field">
          Valor de referência (R$)
          <input v-model.number="newThreshold" type="number" min="0.01" step="0.01" />
        </label>
        <label v-if="needsDays(newType)" class="form-field">
          Dias de antecedência
          <input v-model.number="newDays" type="number" min="1" max="90" />
        </label>
      </div>

      <p v-if="formError" class="form-error">{{ formError }}</p>

      <button class="btn-primary" :disabled="formLoading" @click="createAlert">
        {{ formLoading ? 'Salvando...' : 'Salvar Alerta' }}
      </button>
    </div>

    <!-- Estado de carregamento ─────────────────────────────────────────── -->
    <p v-if="error" class="form-error">{{ error }}</p>
    <div v-if="loading" class="loading-state">Carregando...</div>

    <!-- Lista vazia ────────────────────────────────────────────────────── -->
    <div v-if="!loading && alerts.length === 0" class="empty-state">
      Nenhum alerta configurado. Clique em "Novo Alerta" para começar.
    </div>

    <!-- Lista de alertas ───────────────────────────────────────────────── -->
    <div v-if="!loading && alerts.length > 0" class="alerts-list">
      <div
        v-for="a in alerts"
        :key="a.id"
        class="alert-card"
        :class="statusClass(a)"
      >
        <div class="alert-main">
          <div class="alert-identity">
            <span class="alert-ticker">{{ a.ticker }}</span>
            <span class="alert-desc">{{ alertDescription(a) }}</span>
          </div>

          <div class="alert-meta">
            <span
              class="status-badge"
              :class="statusClass(a)"
            >
              {{ a.is_active ? (a.triggered_at ? 'Disparado' : 'Ativo') : 'Inativo' }}
            </span>
            <span v-if="a.triggered_at" class="triggered-date">
              Último disparo: {{ fmtDate(a.triggered_at) }}
            </span>
          </div>
        </div>

        <div class="alert-actions">
          <button
            class="btn-toggle"
            :class="{ active: a.is_active }"
            @click="toggleAlert(a)"
            :title="a.is_active ? 'Desativar' : 'Ativar'"
          >
            {{ a.is_active ? 'Desativar' : 'Ativar' }}
          </button>
          <button class="btn-delete" @click="deleteAlert(a.id)" title="Remover">
            Remover
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.action-bar {
  margin-bottom: 20px;
}

.btn-primary {
  padding: 10px 20px;
  border-radius: 10px;
  border: none;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 0.9rem;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* ── Form ───────────────────────────────────────────────────────────────── */

.form-card {
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 28px;
}

.form-card h3 {
  margin: 0 0 16px;
  font-size: 1.1rem;
  color: #93c5fd;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 12px;
}

@media (max-width: 600px) {
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

.type-description {
  font-size: 0.82rem;
  color: #64748b;
  margin: 0 0 12px;
}

.form-error {
  color: #f87171;
  font-size: 0.875rem;
  margin: 0 0 12px;
}

/* ── Lista ──────────────────────────────────────────────────────────────── */

.loading-state {
  color: #64748b;
  padding: 24px 0;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: #64748b;
  border: 1px dashed rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  margin-top: 8px;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alert-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 14px;
  flex-wrap: wrap;
  transition: border-color 0.15s;
}

.alert-card.triggered {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.04);
}

.alert-card.inactive {
  opacity: 0.55;
}

.alert-main {
  display: flex;
  align-items: center;
  gap: 24px;
  flex: 1;
  flex-wrap: wrap;
}

.alert-identity {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 120px;
}

.alert-ticker {
  font-size: 1rem;
  font-weight: 700;
  color: #93c5fd;
}

.alert-desc {
  font-size: 0.85rem;
  color: #94a3b8;
}

.alert-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.status-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}

.status-badge.active {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.status-badge.triggered {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}

.status-badge.inactive {
  background: rgba(148, 163, 184, 0.1);
  color: #64748b;
}

.triggered-date {
  font-size: 0.75rem;
  color: #64748b;
}

.alert-actions {
  display: flex;
  gap: 8px;
}

.btn-toggle {
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s;
}

.btn-toggle:hover {
  background: rgba(59, 130, 246, 0.1);
  color: #93c5fd;
}

.btn-delete {
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.2);
  background: transparent;
  color: #f87171;
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s;
}

.btn-delete:hover {
  background: rgba(239, 68, 68, 0.1);
}
</style>
