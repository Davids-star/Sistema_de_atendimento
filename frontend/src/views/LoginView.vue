<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'
import AuthShell from '../components/AuthShell.vue'
import { renderGoogleButton } from '../utils/google'

const router = useRouter()
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const googleEnabled = ref(false)
const googleEl = ref(null)

async function enter(request, friendly401) {
  error.value = ''
  loading.value = true
  try {
    const data = await request()
    setToken(data.access_token)
    router.push({ name: 'dashboard' })
  } catch (e) {
    error.value = e.status === 401 && friendly401 ? friendly401 : e.message
  } finally {
    loading.value = false
  }
}

const submit = () => enter(
  () => api('/auth/login', { method: 'POST', body: { email: email.value, password: password.value } }),
  'E-mail ou senha incorretos.')
const onGoogle = (credential) => enter(() => api('/auth/google', { method: 'POST', body: { credential } }))

// O botão só aparece se o servidor tiver o login com Google configurado e o script do Google carregar.
onMounted(async () => {
  try {
    const cfg = await api('/auth/config')
    if (!cfg.google_client_id) return
    googleEnabled.value = true
    await nextTick()
    await renderGoogleButton(googleEl.value, cfg.google_client_id, onGoogle)
  } catch {
    googleEnabled.value = false   // sem internet/Google bloqueado: o login por senha continua funcionando
  }
})
</script>

<template>
  <AuthShell>
    <h1 class="page-title">Entrar</h1>
    <p class="text-body-medium text-medium-emphasis mt-1 mb-6">Acesse o painel administrativo.</p>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="comfortable" :text="error" />
    <template v-if="googleEnabled">
      <div ref="googleEl" class="google-btn" />
      <div class="or"><span>ou entre com e-mail</span></div>
    </template>

    <v-form @submit.prevent="submit">
      <v-text-field v-model="email" label="E-mail" type="email" autocomplete="username" autofocus />
      <v-text-field v-model="password" label="Senha" :type="showPassword ? 'text' : 'password'" autocomplete="current-password"
                    :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                    @click:append-inner="showPassword = !showPassword" />
      <div class="text-right mb-4 mt-n2">
        <router-link :to="{ name: 'forgot' }" class="link">Esqueci minha senha</router-link>
      </div>
      <v-btn type="submit" color="primary" size="x-large" block :loading="loading" :disabled="!email || !password">
        Entrar
      </v-btn>
    </v-form>
  </AuthShell>
</template>

<style scoped>
.google-btn { min-height: 44px; display: flex; justify-content: center; }
.or { display: flex; align-items: center; gap: 12px; margin: 18px 0; font-size: 0.8rem; color: rgba(var(--v-theme-on-surface), 0.55); }
.or::before, .or::after { content: ''; flex: 1; height: 1px; background: rgba(var(--v-theme-on-surface), 0.12); }
.link { font-size: 0.85rem; color: #8a6420; text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
