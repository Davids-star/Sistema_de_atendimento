<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay, useTheme } from 'vuetify'
import { api, setToken } from '../api'
import { saveTheme } from '../plugins/vuetify'
import { toast } from '../utils/notify'

const router = useRouter()
const theme = useTheme()
const { mdAndUp } = useDisplay()
const drawer = ref(mdAndUp.value)
const admin = ref(null)

const nav = [
  { title: 'Dashboard', icon: 'mdi-view-dashboard-outline', to: { name: 'dashboard' }, exact: true },
  { title: 'Agendamentos', icon: 'mdi-calendar-month-outline', to: { name: 'appointments' } },
  { title: 'Serviços', icon: 'mdi-content-cut', to: { name: 'services' } },
  { title: 'Clientes', icon: 'mdi-account-multiple-outline', to: { name: 'clients' } },
  { title: 'Configurações', icon: 'mdi-cog-outline', to: { name: 'settings' } },
]

const isDark = computed(() => theme.current.value.dark)
function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  theme.change(next)
  saveTheme(next)
}
const initial = computed(() => (admin.value?.name ?? '?').trim().charAt(0).toUpperCase())

onMounted(async () => {
  try { admin.value = await api('/auth/me') } catch { /* 401 já redireciona para o login */ }
})

async function logout() {
  try { await api('/auth/logout', { method: 'POST' }) } catch { /* o token é descartado de qualquer forma */ }
  setToken(null)
  router.push({ name: 'login' })
}
</script>

<template>
  <v-navigation-drawer v-model="drawer" :permanent="mdAndUp" width="256" theme="dark" class="sidebar">
    <div class="brand">
      <div class="brand-mark"><v-icon icon="mdi-content-cut" size="22" /></div>
      <div>
        <div class="brand-name">Barbearia</div>
        <div class="brand-sub">Painel</div>
      </div>
    </div>
    <v-list nav>
      <v-list-item v-for="item in nav" :key="item.title" :to="item.to" :exact="item.exact" :prepend-icon="item.icon"
                   :title="item.title" @click="!mdAndUp && (drawer = false)" />
    </v-list>
    <template #append>
      <div class="sidebar-foot">Agendamentos pelo WhatsApp e pelo painel</div>
    </template>
  </v-navigation-drawer>

  <v-app-bar flat class="app-bar" height="64">
    <v-app-bar-nav-icon v-if="!mdAndUp" @click="drawer = !drawer" />
    <v-spacer />
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
