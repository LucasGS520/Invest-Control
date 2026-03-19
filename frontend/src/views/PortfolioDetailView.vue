<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const portfolioId = route.params.id
</script>

<template>
  <div class="page-container">
    <h2>Carteira #{{ portfolioId }}</h2>
    <p class="coming-soon">Detalhes da carteira, ativos e transações.</p>
    <div class="placeholder-badge">Em implementação — Fase 1</div>
  </div>
</template>
