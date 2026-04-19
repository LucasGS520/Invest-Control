import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/registro',
      name: 'registro',
      component: () => import('@/views/RegisterView.vue'),
      meta: { public: true },
    },
    {
      path: '/aporte',
      name: 'aporte',
      component: () => import('@/views/AporteView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/carteiras',
      name: 'carteiras',
      component: () => import('@/views/PortfoliosView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/carteiras/:id',
      name: 'carteira-detalhe',
      component: () => import('@/views/PortfolioDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/alertas',
      name: 'alertas',
      component: () => import('@/views/AlertsView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

// Guarda de navegação: redireciona para login se não autenticado.
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.public && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
