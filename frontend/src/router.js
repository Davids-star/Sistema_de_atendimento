import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api'
import { loadUser } from './session'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
  { path: '/esqueci-senha', name: 'forgot', component: () => import('./views/ForgotPasswordView.vue') },
  { path: '/redefinir-senha', name: 'reset', component: () => import('./views/ResetPasswordView.vue') },
  { path: '/confirmar-email', name: 'confirm-email', component: () => import('./views/ConfirmEmailView.vue') },
  // Passos de quem entrou mas ainda não pode usar o painel (precisam de login, não de acesso liberado).
  { path: '/completar-perfil', name: 'complete-profile', meta: { requiresAuth: true }, component: () => import('./views/CompleteProfileView.vue') },
  { path: '/aguardando-liberacao', name: 'pending', meta: { requiresAuth: true }, component: () => import('./views/PendingApprovalView.vue') },
  {
    path: '/',
    component: () => import('./layouts/AppLayout.vue'),
    meta: { requiresAuth: true, panel: true },
    children: [
      { path: '', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
      { path: 'agendamentos', name: 'appointments', component: () => import('./views/AppointmentsView.vue') },
      { path: 'servicos', name: 'services', component: () => import('./views/ServicesView.vue') },
      { path: 'clientes', name: 'clients', component: () => import('./views/ClientsView.vue') },
      { path: 'usuarios', name: 'users', meta: { ownerOnly: true }, component: () => import('./views/UsersView.vue') },
      { path: 'configuracoes', name: 'settings', component: () => import('./views/SettingsView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

// Decide para onde cada pessoa vai. Ordem: estar logado -> informar o celular -> ter o acesso liberado.
export async function guard(to) {
  const token = getToken()
  const protectedRoute = to.matched.some((r) => r.meta.requiresAuth)
  if (protectedRoute && !token) return { name: 'login' }
  if (!token || (!protectedRoute && to.name !== 'login')) return   // páginas públicas

  const user = await loadUser()
  if (!user) return protectedRoute ? { name: 'login' } : undefined   // token inválido
  if (to.name === 'login') return { name: 'dashboard' }               // já logado: a regra abaixo reencaminha

  const home = user.approved ? 'dashboard' : 'pending'
  if (to.name === 'complete-profile') return user.phone ? { name: home } : undefined
  if (!user.phone) return { name: 'complete-profile' }
  if (to.name === 'pending') return user.approved ? { name: 'dashboard' } : undefined
  if (!user.approved) return { name: 'pending' }
  if (to.meta.ownerOnly && !user.is_owner) return { name: 'dashboard' }
}

const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(guard)

export default router
