<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.append('username', email.value)
    params.append('password', password.value)
    const { data } = await axios.post('/api/auth/login', params)
    auth.setToken(data.access_token)
    const redirect = (route.query.redirect as string) || '/aporte'
    router.push(redirect)
  } catch {
    error.value = 'E-mail ou senha inválidos.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>InvestControl</h1>
      <p class="subtitle">Entre na sua conta</p>

      <form @submit.prevent="handleLogin" class="auth-form">
        <label>
          E-mail
          <input v-model="email" type="email" placeholder="seu@email.com" required />
        </label>
        <label>
          Senha
          <input v-model="password" type="password" placeholder="••••••••" required />
        </label>
        <p v-if="error" class="form-error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Entrando...' : 'Entrar' }}
        </button>
      </form>

      <p class="auth-link">
        Não tem conta?
        <router-link to="/registro">Cadastre-se</router-link>
      </p>
    </div>
  </div>
</template>
