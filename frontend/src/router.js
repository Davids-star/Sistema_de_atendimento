import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
  { path: '/esqueci-senha', name: 'forgot', component: () => import('./views/ForgotPasswordView.vue') },
  { path: '/redefinir-senha', name: 'reset', component: () => import('./views/ResetPasswordView.vue') },
  {
    path: '/',
    component: () => import('./layouts/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
      { path: 'agendamentos', name: 'appointments', component: () => import('./views/AppointmentsView.vue') },
      { path: 'servicos', name: 'services', component: () => import('./views/ServicesView.vue') },
      { path: 'clientes', name: 'clients', component: () => import('./views/ClientsView.vue') },
      { path: 'configuracoes', name: 'settings', component: () => import('./views/SettingsView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (to.matched.some((r) => r.meta.requiresAuth) && !getToken()) {
    return { name: 'login' }
  }
  if (to.name === 'login' && getToken()) return { name: 'dashboard' }
})

export default router
