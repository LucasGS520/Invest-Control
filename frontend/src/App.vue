<script setup lang="ts">
const modules = [
  {
    title: 'Aporte sob demanda',
    description:
      'Receber um valor disponível e retornar recomendações explicadas com base em dividendos, preço-teto e carteira atual.',
  },
  {
    title: 'Carteiras e transações',
    description:
      'Cadastrar ativos, registrar movimentações e consolidar métricas como preço médio e rentabilidade.',
  },
  {
    title: 'Dados de mercado',
    description:
      'Preparar integrações com cotações, proventos, histórico e regras de atualização com cache.',
  },
]
</script>

<template>
  <main class="page-shell">
    <section class="hero-card">
      <span class="badge">MVP em preparação</span>
      <h1>InvestControl</h1>
      <p class="hero-text">
        A fundação do projeto foi criada a partir do SRS para iniciar o desenvolvimento do ecossistema de
        aporte sob demanda com foco em dividendos.
      </p>

      <div class="status-grid">
        <article>
          <strong>Backend</strong>
          <span>FastAPI pronta para evoluir a API REST</span>
        </article>
        <article>
          <strong>Frontend</strong>
          <span>Vue.js + Vite com tela inicial do produto</span>
        </article>
        <article>
          <strong>Infra local</strong>
          <span>Docker Compose com PostgreSQL e serviços integrados</span>
        </article>
      </div>
    </section>

    <section class="modules-section">
      <header>
        <p class="section-label">Primeira iteração</p>
        <h2>Módulos priorizados para o MVP</h2>
      </header>

      <div class="module-grid">
        <article v-for="module in modules" :key="module.title" class="module-card">
          <h3>{{ module.title }}</h3>
          <p>{{ module.description }}</p>
        </article>
      </div>
    </section>
  </main>
</template>
