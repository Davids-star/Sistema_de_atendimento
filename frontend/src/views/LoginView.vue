<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'

const router = useRouter()
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const data = await api('/auth/login', { method: 'POST', body: { email: email.value, password: password.value } })
    setToken(data.access_token)
    router.push({ name: 'dashboard' })
  } catch (e) {
    error.value = e.status === 401 ? 'E-mail ou senha incorretos.' : e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-main class="d-flex align-center justify-center">
    <v-card width="400" max-width="92vw" class="pa-6">
      <div class="text-center mb-6">
        <v-icon icon="mdi-content-cut" size="40" color="primary" />
        <h1 class="text-headline-small mt-2">Painel da Barbearia</h1>
        <p class="text-body-medium text-medium-emphasis">Entre para gerenciar seus agendamentos</p>
      </div>

      <v-form @submit.prevent="submit">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" :text="error" />
        <v-text-field v-model="email" label="E-mail" type="email" autocomplete="username"
                      prepend-inner-icon="mdi-email-outline" required />
        <v-text-field v-model="password" label="Senha" type="password" autocomplete="current-password"
                      prepend-inner-icon="mdi-lock-outline" required />
        <v-btn type="submit" color="primary" size="large" block :loading="loading"
               :disabled="!email || !password">Entrar</v-btn>
      </v-form>
    </v-card>
  </v-main>
</template>
