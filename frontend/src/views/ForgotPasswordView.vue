<script setup>
import { ref } from 'vue'
import { api } from '../api'
import AuthShell from '../components/AuthShell.vue'

const email = ref('')
const loading = ref(false)
const error = ref('')
const sent = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await api('/auth/forgot-password', { method: 'POST', body: { email: email.value } })
    sent.value = true   // a API responde igual exista o e-mail ou não; nós também
  } catch (e) {
    error.value = e.message   // ex.: 429 "Muitas tentativas"
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell>
    <h1 class="page-title">Esqueci minha senha</h1>

    <template v-if="!sent">
      <p class="text-body-medium text-medium-emphasis mt-1 mb-6">
        Informe o e-mail do painel. Se ele estiver cadastrado, enviaremos um link para criar uma nova senha.
      </p>
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="comfortable" :text="error" />
      <v-form @submit.prevent="submit">
        <v-text-field v-model="email" label="E-mail" type="email" autocomplete="username" autofocus />
        <v-btn type="submit" color="primary" size="x-large" block :loading="loading" :disabled="!email">Enviar link</v-btn>
      </v-form>
    </template>

    <template v-else>
      <v-alert type="success" variant="tonal" class="mt-4 mb-4" icon="mdi-email-check-outline">
        Se o e-mail estiver cadastrado, enviamos as instruções. O link vale por 30 minutos e só pode ser usado uma vez.
        Confira também a caixa de spam.
      </v-alert>
    </template>

    <div class="mt-6">
      <router-link :to="{ name: 'login' }" class="link"><v-icon icon="mdi-arrow-left" size="14" /> Voltar para o login</router-link>
    </div>
  </AuthShell>
</template>

<style scoped>
.link { font-size: 0.9rem; color: var(--link); text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
