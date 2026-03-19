import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export interface Portfolio {
  id: number
  name: string
  description: string | null
  created_at: string
}

export const usePortfolioStore = defineStore('portfolio', () => {
  const portfolios = ref<Portfolio[]>([])
  const loading = ref(false)

  async function fetchPortfolios() {
    loading.value = true
    try {
      const { data } = await axios.get('/api/portfolios/')
      portfolios.value = data
    } finally {
      loading.value = false
    }
  }

  async function createPortfolio(payload: { name: string; description?: string }) {
    const { data } = await axios.post('/api/portfolios/', payload)
    portfolios.value.push(data)
    return data as Portfolio
  }

  async function deletePortfolio(id: number) {
    await axios.delete(`/api/portfolios/${id}`)
    portfolios.value = portfolios.value.filter((p) => p.id !== id)
  }

  return { portfolios, loading, fetchPortfolios, createPortfolio, deletePortfolio }
})
