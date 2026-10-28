import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
  {
    path: '/',
    component: () => import('./layouts/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
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
