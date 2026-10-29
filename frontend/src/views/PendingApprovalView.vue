<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'
import AuthShell from '../components/AuthShell.vue'
import { loadUser, resetSession, session } from '../session'

const router = useRouter()
const checking = ref(false)
const stillWaiting = ref(false)

async function check() {
  checking.value = true
  stillWaiting.value = false
  const user = await loadUser({ force: true })
  checking.value = false
  if (user?.approved) router.push({ name: 'dashboard' })
  else stillWaiting.value = true
}

async function leave() {
  try { await api('/auth/logout', { method: 'POST' }) } catch { /* o token é descartado de qualquer forma */ }
  setToken(null); resetSession()
  router.push({ name: 'login' })
}
</script>

<template>
  <AuthShell>
    <h1 class="page-title">Aguardando liberação</h1>
    <v-alert type="info" variant="tonal" class="mt-4 mb-4" icon="mdi-shield-lock-outline">
      <strong>Sua conta foi criada{{ session.user ? `, ${session.user.name.split(' ')[0]}` : '' }}.</strong>
      O acesso ao painel só é liberado pelo dono. Assim que ele liberar, você já poderá entrar.
    </v-alert>
    <v-btn color="primary" size="x-large" block :loading="checking" @click="check">Verificar novamente</v-btn>
    <p v-if="stillWaiting" class="text-body-medium text-medium-emphasis mt-3">Ainda não foi liberado. Avise o dono e tente de novo.</p>
    <div class="mt-6"><a href="#" class="link" @click.prevent="leave">Sair</a></div>
  </AuthShell>
</template>

<style scoped>
.link { font-size: 0.9rem; color: var(--link); text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
