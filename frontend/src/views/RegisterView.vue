<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const name = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleRegister() {
  error.value = ''
  loading.value = true
  try {
    await axios.post('/api/auth/register', {
      name: name.value,
      email: email.value,
      password: password.value,
    })
    // Faz login automático após cadastro
    const params = new URLSearchParams()
    params.append('username', email.value)
    params.append('password', password.value)
    const { data } = await axios.post('/api/auth/login', params)
    auth.setToken(data.access_token)
    router.push('/dashboard')
  } catch (err: unknown) {
    const axiosError = err as { response?: { data?: { detail?: string } } }
    error.value = axiosError.response?.data?.detail || 'Erro ao criar conta.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1>InvestControl</h1>
      <p class="subtitle">Crie sua conta</p>

      <form @submit.prevent="handleRegister" class="auth-form">
        <label>
          Nome
          <input v-model="name" type="text" placeholder="Seu nome" required />
        </label>
        <label>
          E-mail
          <input v-model="email" type="email" placeholder="seu@email.com" required />
        </label>
        <label>
          Senha
          <input v-model="password" type="password" placeholder="Mínimo 8 caracteres" required minlength="8" />
        </label>
        <p v-if="error" class="form-error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Criando...' : 'Criar Conta' }}
        </button>
      </form>

      <p class="auth-link">
        Já tem conta?
        <router-link to="/login">Faça login</router-link>
      </p>
    </div>
  </div>
</template>
