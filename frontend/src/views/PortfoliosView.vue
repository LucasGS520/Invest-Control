<script setup lang="ts">
// Gestão de Carteiras (FR2)
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePortfolioStore } from '@/stores/portfolio'

const router = useRouter()
const portfolioStore = usePortfolioStore()

const showForm = ref(false)
const newName = ref('')
const newDescription = ref('')
const newObjective = ref('')
const formLoading = ref(false)
const formError = ref('')

// For rename
const editingId = ref<number | null>(null)
const editName = ref('')

onMounted(() => portfolioStore.fetchPortfolios())

async function createPortfolio() {
  if (!newName.value.trim()) {
    formError.value = 'Informe um nome para a carteira.'
    return
  }
  formLoading.value = true
  formError.value = ''
  try {
    await portfolioStore.createPortfolio({
      name: newName.value.trim(),
      description: newDescription.value.trim() || undefined,
      objective: newObjective.value.trim() || undefined,
    })
    newName.value = ''
    newDescription.value = ''
    newObjective.value = ''
    showForm.value = false
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    formError.value = e.response?.data?.detail || 'Erro ao criar carteira.'
  } finally {
    formLoading.value = false
  }
}

async function deletePortfolio(id: number, name: string) {
  if (!confirm(`Remover a carteira "${name}"? Esta ação é irreversível.`)) return
  try {
    await portfolioStore.deletePortfolio(id)
  } catch {
    // silently ignore
  }
}

function openDetail(id: number) {
  router.push(`/carteiras/${id}`)
}

function fmt(dt: string): string {
  return new Date(dt).toLocaleDateString('pt-BR')
}
</script>

<template>
  <div class="page-container">
    <h2>Minhas Carteiras</h2>
    <p class="coming-soon">Gerencie suas carteiras, ativos e transações.</p>

    <!-- Barra de ações ─────────────────────────────────────────────────── -->
    <div class="action-bar">
      <button class="btn-primary" @click="showForm = !showForm">
        {{ showForm ? 'Cancelar' : '+ Nova Carteira' }}
      </button>
    </div>

    <!-- Formulário de criação ──────────────────────────────────────────── -->
    <div v-if="showForm" class="form-card">
      <h3>Nova Carteira</h3>
      <div class="form-row">
        <label class="form-field">
          Nome
          <input v-model="newName" type="text" placeholder="ex: FIIs de Renda" maxlength="120" />
        </label>
        <label class="form-field">
          Descrição (opcional)
          <input v-model="newDescription" type="text" placeholder="Breve descrição" />
        </label>
        <label class="form-field">
          Objetivo (opcional)
          <input v-model="newObjective" type="text" placeholder="ex: Renda passiva" maxlength="200" />
        </label>
      </div>
      <p v-if="formError" class="form-error">{{ formError }}</p>
      <button class="btn-primary" :disabled="formLoading" @click="createPortfolio">
        {{ formLoading ? 'Salvando...' : 'Salvar' }}
      </button>
    </div>

    <!-- Estado de carregamento ─────────────────────────────────────────── -->
    <div v-if="portfolioStore.loading" class="loading-state">Carregando...</div>

    <!-- Lista vazia ────────────────────────────────────────────────────── -->
    <div
      v-if="!portfolioStore.loading && portfolioStore.portfolios.length === 0"
      class="empty-state"
    >
      Nenhuma carteira criada. Clique em "Nova Carteira" para começar.
    </div>

    <!-- Grade de carteiras ─────────────────────────────────────────────── -->
    <div v-if="portfolioStore.portfolios.length > 0" class="portfolios-grid">
      <div
        v-for="p in portfolioStore.portfolios"
        :key="p.id"
        class="portfolio-card"
        @click="openDetail(p.id)"
      >
        <div class="portfolio-card-header">
          <span class="portfolio-name">{{ p.name }}</span>
          <span class="portfolio-id">#{{ p.id }}</span>
        </div>

        <p v-if="p.description" class="portfolio-description">{{ p.description }}</p>
        <p v-if="p.objective" class="portfolio-objective">🎯 {{ p.objective }}</p>

        <div class="portfolio-meta">
          <span class="meta-item">Criada em {{ fmt(p.created_at) }}</span>
          <span class="meta-item currency-badge">{{ p.currency ?? 'BRL' }}</span>
        </div>

        <div class="portfolio-actions" @click.stop>
          <button class="btn-detail" @click="openDetail(p.id)">Ver detalhes</button>
          <button class="btn-delete-sm" @click="deletePortfolio(p.id, p.name)">Remover</button>
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
  font-size: 0.9rem;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }

.form-card {
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 28px;
}

.form-card h3 {
  margin: 0 0 16px;
  font-size: 1.05rem;
  color: #93c5fd;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 12px;
}

@media (max-width: 600px) {
  .form-row { grid-template-columns: 1fr; }
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.9rem;
  color: #cbd5e1;
}

.form-field input {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.6);
  color: #e5eefc;
  outline: none;
  transition: border-color 0.15s;
}

.form-field input:focus { border-color: #3b82f6; }
.form-error { color: #f87171; font-size: 0.875rem; margin: 0 0 12px; }

.loading-state { color: #64748b; padding: 24px 0; }

.empty-state {
  padding: 40px;
  text-align: center;
  color: #64748b;
  border: 1px dashed rgba(148, 163, 184, 0.2);
  border-radius: 16px;
}

/* ── Grade ──────────────────────────────────────────────────────────────── */

.portfolios-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.portfolio-card {
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.12s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.portfolio-card:hover {
  border-color: rgba(59, 130, 246, 0.4);
  transform: translateY(-2px);
}

.portfolio-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.portfolio-name {
  font-size: 1.05rem;
  font-weight: 700;
  color: #93c5fd;
}

.portfolio-id {
  font-size: 0.75rem;
  color: #475569;
}

.portfolio-description {
  font-size: 0.85rem;
  color: #94a3b8;
  margin: 0;
}

.portfolio-meta {
  margin-top: auto;
}

.meta-item {
  font-size: 0.78rem;
  color: #64748b;
}

.portfolio-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.btn-detail {
  flex: 1;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.1);
  color: #93c5fd;
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s;
}

.btn-detail:hover { background: rgba(59, 130, 246, 0.2); }

.btn-delete-sm {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.2);
  background: transparent;
  color: #f87171;
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s;
}

.btn-delete-sm:hover { background: rgba(239, 68, 68, 0.1); }
</style>
