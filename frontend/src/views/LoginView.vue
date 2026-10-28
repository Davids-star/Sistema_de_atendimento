<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'
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
  <v-main class="login">
    <aside class="hero">
      <div class="pole" aria-hidden="true" />
      <div class="hero-inner">
        <div class="brand-mark"><v-icon icon="mdi-content-cut" size="26" /></div>
        <h2>Sua agenda,<br />sem complicação.</h2>
        <p>Horários, clientes e faturamento da barbearia em um só lugar, com atendimento automático pelo WhatsApp.</p>
      </div>
    </aside>

    <section class="form-side">
      <div class="form-box">
        <div class="mobile-brand">
          <div class="brand-mark"><v-icon icon="mdi-content-cut" size="22" /></div>
          <span>Barbearia</span>
        </div>
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
          <v-btn type="submit" color="primary" size="x-large" block :loading="loading" :disabled="!email || !password" class="mt-2">
            Entrar
          </v-btn>
        </v-form>
      </div>
    </section>
  </v-main>
</template>

<style scoped>
.google-btn { min-height: 44px; display: flex; justify-content: center; }
.or { display: flex; align-items: center; gap: 12px; margin: 18px 0; font-size: 0.8rem; color: rgba(var(--v-theme-on-surface), 0.55); }
.or::before, .or::after { content: ''; flex: 1; height: 1px; background: rgba(var(--v-theme-on-surface), 0.12); }
.login { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); min-height: 100vh; }
.hero { position: relative; overflow: hidden; background: var(--ink); color: #f3ece0; display: flex; align-items: center; padding: 64px; }
.hero::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(900px 500px at 15% 10%, rgba(215, 174, 98, 0.16), transparent 60%),
              radial-gradient(700px 500px at 100% 100%, rgba(127, 163, 199, 0.12), transparent 60%);
}
/* "Poste de barbeiro": faixas diagonais finas na lateral */
.pole {
  position: absolute; right: 0; top: 0; bottom: 0; width: 18px; opacity: 0.9;
  background: repeating-linear-gradient(135deg, #d7ae62 0 10px, #f3ece0 10px 20px, #2c6a8f 20px 30px, #f3ece0 30px 40px);
}
.hero-inner { position: relative; max-width: 460px; }
.hero .brand-mark { margin-bottom: 28px; }
.hero h2 { font-family: var(--font-display); font-weight: 600; font-size: 3rem; line-height: 1.08; letter-spacing: -0.02em; margin-bottom: 18px; }
.hero p { font-size: 1.05rem; line-height: 1.6; color: rgba(243, 236, 224, 0.72); }
.brand-mark { width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; background: linear-gradient(145deg, #d7ae62, #a97c2f); color: #1a1408; }

.form-side { display: flex; align-items: center; justify-content: center; padding: 32px; }
.form-box { width: 100%; max-width: 400px; }
.mobile-brand { display: none; align-items: center; gap: 10px; margin-bottom: 28px; font-family: var(--font-display); font-weight: 600; font-size: 1.3rem; }
.mobile-brand .brand-mark { width: 38px; height: 38px; border-radius: 11px; }

@media (max-width: 900px) {
  .login { grid-template-columns: minmax(0, 1fr); }
  .hero { display: none; }
  .mobile-brand { display: flex; }
}
</style>
