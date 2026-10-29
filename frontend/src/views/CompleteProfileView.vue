<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'
import AuthShell from '../components/AuthShell.vue'
import { resetSession, session } from '../session'
import { phoneError } from '../utils/phone'

const router = useRouter()
const phone = ref('')
const loading = ref(false)
const error = ref('')
const problem = computed(() => phoneError(phone.value))

async function save() {
  if (problem.value) return
  error.value = ''
  loading.value = true
  try {
    session.user = await api('/auth/me', { method: 'PATCH', body: { phone: phone.value } })
    router.push({ name: 'dashboard' })   // o roteador reencaminha para "aguardando" se o acesso ainda não foi liberado
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function leave() {
  try { await api('/auth/logout', { method: 'POST' }) } catch { /* o token é descartado de qualquer forma */ }
  setToken(null); resetSession()
  router.push({ name: 'login' })
}
</script>

<template>
  <AuthShell>
    <h1 class="page-title">Quase lá{{ session.user ? `, ${session.user.name.split(' ')[0]}` : '' }}</h1>
    <p class="text-body-medium text-medium-emphasis mt-1 mb-6">
      Para continuar, informe o seu número de celular (com WhatsApp). Ele identifica você no sistema.
    </p>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="comfortable" :text="error" />
    <v-form @submit.prevent="save">
      <v-text-field v-model="phone" label="Celular (WhatsApp)" inputmode="tel" autocomplete="tel" autofocus
                    prepend-inner-icon="mdi-whatsapp" :error-messages="phone && problem ? problem : ''" />
      <v-btn type="submit" color="primary" size="x-large" block :loading="loading" :disabled="!!problem">Continuar</v-btn>
    </v-form>
    <div class="mt-6"><a href="#" class="link" @click.prevent="leave">Sair</a></div>
  </AuthShell>
</template>

<style scoped>
.link { font-size: 0.9rem; color: #8a6420; text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
