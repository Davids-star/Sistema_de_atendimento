<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay, useTheme } from 'vuetify'
import { api, setToken } from '../api'
import { BRAND } from '../brand'
import { saveTheme } from '../plugins/vuetify'
import NotificationBell from '../components/NotificationBell.vue'
import { inbox, resetInbox, startPolling, stopPolling } from '../notifications'
import { setupPush, unregisterDevice } from '../push'
import { loadUser, resetSession, session } from '../session'
import { toast } from '../utils/notify'

const router = useRouter()
const theme = useTheme()
const { mdAndUp } = useDisplay()
const drawer = ref(mdAndUp.value)
const admin = computed(() => session.user)
const pendingUsers = ref(0)   // só o dono vê: pessoas aguardando liberação

const nav = [
  { title: 'Dashboard', icon: 'mdi-view-dashboard-outline', to: { name: 'dashboard' }, exact: true },
  { title: 'Agendamentos', icon: 'mdi-calendar-month-outline', to: { name: 'appointments' } },
  { title: 'Atendimento', icon: 'mdi-message-alert-outline', to: { name: 'handoff' }, badge: 'handoff' },
  { title: 'Serviços', icon: 'mdi-shimmer', to: { name: 'services' } },
  { title: 'Clientes', icon: 'mdi-account-multiple-outline', to: { name: 'clients' } },
  { title: 'Usuários', icon: 'mdi-shield-account-outline', to: { name: 'users' }, ownerOnly: true },
  { title: 'Configurações', icon: 'mdi-cog-outline', to: { name: 'settings' } },
]
// Quantos pedidos de atendimento ainda não lidos (vem dos avisos do sino).
const waiting = computed(() => inbox.items.filter((n) => n.kind === 'handoff' && !n.read_at).length)
const visibleNav = computed(() => nav.filter((i) => !i.ownerOnly || admin.value?.is_owner))

const isDark = computed(() => theme.current.value.dark)
function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  theme.change(next)
  saveTheme(next)
}
const initial = computed(() => (admin.value?.name ?? '?').trim().charAt(0).toUpperCase())

onMounted(async () => {
  startPolling()   // avisos do sino enquanto o painel estiver aberto
  const user = await loadUser()   // 401 já redireciona para o login
  if (user) setupPush({ router })   // no app Android: pede permissão e registra o aparelho para receber avisos com o app fechado
  if (user?.is_owner) {
    try { pendingUsers.value = (await api('/users', { params: { status: 'pending_approval' } })).length } catch { /* só um aviso */ }
  }
})

onBeforeUnmount(stopPolling)

async function logout() {
  await unregisterDevice()   // antes de apagar o login: precisa estar autenticado
  try { await api('/auth/logout', { method: 'POST' }) } catch { /* o token é descartado de qualquer forma */ }
  setToken(null)
  resetSession()
  resetInbox()   // a próxima pessoa não herda os avisos desta
  router.push({ name: 'login' })
}
</script>

<template>
  <v-navigation-drawer v-model="drawer" :permanent="mdAndUp" width="256" theme="dark" class="sidebar">
    <div class="brand">
      <div class="brand-mark"><v-icon :icon="BRAND.icon" size="22" /></div>
      <div>
        <div class="brand-name">{{ BRAND.name }}</div>
        <div class="brand-sub">Painel</div>
      </div>
    </div>
    <v-list nav>
      <v-list-item v-for="item in visibleNav" :key="item.title" :to="item.to" :exact="item.exact" :prepend-icon="item.icon"
                   :title="item.title" @click="!mdAndUp && (drawer = false)">
        <template v-if="(item.ownerOnly && pendingUsers) || (item.badge === 'handoff' && waiting)" #append>
          <span class="nav-badge">{{ item.badge === 'handoff' ? waiting : pendingUsers }}</span>
        </template>
      </v-list-item>
    </v-list>
    <template #append>
      <div class="sidebar-foot">Agendamentos pelo WhatsApp e pelo painel</div>
    </template>
  </v-navigation-drawer>

  <v-app-bar flat class="app-bar" height="64">
    <v-app-bar-nav-icon v-if="!mdAndUp" @click="drawer = !drawer" />
    <v-spacer />
    <NotificationBell />
    <v-btn :icon="isDark ? 'mdi-weather-sunny' : 'mdi-weather-night'" variant="text" :title="isDark ? 'Tema claro' : 'Tema escuro'"
           @click="toggleTheme" />
    <div v-if="admin" class="d-flex align-center ga-2 mx-2">
      <div class="avatar-initial">{{ initial }}</div>
      <span class="text-body-medium font-weight-medium d-none d-sm-inline">{{ admin.name }}</span>
    </div>
    <v-btn icon="mdi-logout" variant="text" title="Sair" @click="logout" />
  </v-app-bar>

  <v-main>
    <v-container fluid class="page pa-4 pa-md-8">
      <router-view />
    </v-container>
  </v-main>

  <v-snackbar v-model="toast.show" :color="toast.color" :timeout="4000" location="bottom right">{{ toast.text }}</v-snackbar>
</template>

<style scoped>
.page { max-width: 1280px; }
</style>
