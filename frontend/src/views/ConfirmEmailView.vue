<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import AuthShell from '../components/AuthShell.vue'

const route = useRoute()
const state = ref('loading')   // loading | ok | invalid | error
const message = ref('')

onMounted(async () => {
  const token = String(route.query.token ?? '')
  if (!token) { state.value = 'invalid'; return }
  try {
    await api('/auth/verify-email', { method: 'POST', body: { token } })
    state.value = 'ok'
  } catch (e) {
    if (e.status === 400) state.value = 'invalid'
    else { state.value = 'error'; message.value = e.message }
  }
})
</script>

<template>
  <AuthShell>
    <h1 class="page-title">Confirmação de e-mail</h1>

    <div v-if="state === 'loading'" class="mt-6 d-flex align-center ga-3">
      <v-progress-circular indeterminate size="22" width="3" /> Confirmando…
    </div>

    <template v-else-if="state === 'ok'">
      <v-alert type="success" variant="tonal" class="mt-4 mb-4" icon="mdi-check-circle-outline">
        E-mail confirmado! Agora é só entrar. Se o seu acesso ainda não foi liberado, o dono precisa liberar.
      </v-alert>
      <v-btn color="primary" size="x-large" block :to="{ name: 'login' }">Ir para o login</v-btn>
    </template>

    <template v-else-if="state === 'invalid'">
      <v-alert type="error" variant="tonal" class="mt-4 mb-4" icon="mdi-link-off">
        Este link é inválido ou expirou. Cada link vale por 24 horas e só pode ser usado uma vez.
      </v-alert>
      <v-btn color="primary" size="x-large" block :to="{ name: 'login' }">Voltar ao login</v-btn>
      <p class="text-body-small text-medium-emphasis mt-3">Na tela de login, ao tentar entrar, você pode pedir um novo e-mail de confirmação.</p>
    </template>

    <v-alert v-else type="error" variant="tonal" class="mt-4" :text="message" />
  </AuthShell>
</template>
