<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <nav v-if="auth.isAuthenticated" class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">₿</span>
        <span class="brand-name">InvestControl</span>
      </div>
      <ul class="nav-list">
        <li>
          <router-link to="/dashboard" active-class="active">Dashboard</router-link>
        </li>
        <li>
          <router-link to="/aporte" active-class="active">Aporte Sob Demanda</router-link>
        </li>
        <li>
          <router-link to="/carteiras" active-class="active">Carteiras</router-link>
        </li>
        <li>
          <router-link to="/alertas" active-class="active">Alertas</router-link>
        </li>
      </ul>
      <button class="logout-btn" @click="logout">Sair</button>
    </nav>

    <main :class="auth.isAuthenticated ? 'main-content' : 'main-full'">
      <RouterView />
    </main>
  </div>
</template>
