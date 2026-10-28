<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { api, setToken } from '../api'
import { toast } from '../utils/notify'

const router = useRouter()
const { mdAndUp } = useDisplay()
const drawer = ref(mdAndUp.value)
const admin = ref(null)

// Telas já implementadas. As próximas entram aqui conforme forem criadas.
const nav = [
  { title: 'Dashboard', icon: 'mdi-view-dashboard-outline', to: { name: 'dashboard' } },
  { title: 'Agendamentos', icon: 'mdi-calendar-month-outline', to: { name: 'appointments' } },
  { title: 'Serviços', icon: 'mdi-content-cut', to: { name: 'services' } },
  { title: 'Clientes', icon: 'mdi-account-multiple-outline', to: { name: 'clients' } },
  { title: 'Configurações', icon: 'mdi-cog-outline', to: { name: 'settings' } },
]

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
  <v-navigation-drawer v-model="drawer" :permanent="mdAndUp">
    <v-list-item class="py-4" prepend-icon="mdi-content-cut" title="Barbearia" subtitle="Painel administrativo" />
    <v-divider />
    <v-list nav>
      <v-list-item v-for="item in nav" :key="item.title" :to="item.to" :prepend-icon="item.icon"
                   :title="item.title" color="primary" />
    </v-list>
  </v-navigation-drawer>

  <v-app-bar flat border="b">
    <v-app-bar-nav-icon v-if="!mdAndUp" @click="drawer = !drawer" />
    <v-spacer />
    <span v-if="admin" class="text-body-medium text-medium-emphasis mr-2 d-none d-sm-inline">{{ admin.name }}</span>
    <v-btn prepend-icon="mdi-logout" variant="text" @click="logout">Sair</v-btn>
  </v-app-bar>

  <v-main>
    <v-container fluid class="pa-4 pa-md-6">
      <router-view />
    </v-container>
  </v-main>

  <v-snackbar v-model="toast.show" :color="toast.color" :timeout="4000" location="bottom right">{{ toast.text }}</v-snackbar>
</template>
