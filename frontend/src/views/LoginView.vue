<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'
import AuthShell from '../components/AuthShell.vue'
import { resetSession } from '../session'
import { notify, notifyError } from '../utils/notify'
import { passwordError } from '../utils/password'
import { phoneError } from '../utils/phone'
import { renderGoogleButton } from '../utils/google'

const router = useRouter()
const tab = ref('login')   // login | signup

// ---------- entrar ----------
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const needsConfirm = ref(false)   // senha certa, mas o e-mail ainda não foi confirmado
const googleEnabled = ref(false)
const googleEl = ref(null)

async function enter(request, friendly401) {
  error.value = ''
  needsConfirm.value = false
  loading.value = true
  try {
    const data = await request()
    resetSession()   // quem entra nunca herda os dados de quem estava antes
    setToken(data.access_token)
    router.push({ name: 'dashboard' })   // o roteador encaminha: celular -> liberação -> painel
  } catch (e) {
    if (e.status === 403) needsConfirm.value = true
    error.value = e.status === 401 && friendly401 ? friendly401 : e.message
  } finally {
    loading.value = false
  }
}

const submit = () => enter(
  () => api('/auth/login', { method: 'POST', body: { email: email.value, password: password.value } }),
  'E-mail ou senha incorretos.')
const onGoogle = (credential) => enter(() => api('/auth/google', { method: 'POST', body: { credential } }))

async function resend(address) {
  try {
    const r = await api('/auth/resend-verification', { method: 'POST', body: { email: address } })
    notify(r.detail)
  } catch (e) { notifyError(e) }
}

// ---------- criar conta ----------
const form = ref({ name: '', phone: '', email: '', password: '', confirm: '' })
const showSignupPassword = ref(false)
const signing = ref(false)
const signupError = ref('')
const signupDone = ref(false)

const signupProblems = computed(() => ({
  name: form.value.name.trim().length >= 2 ? '' : 'Informe seu nome',
  phone: phoneError(form.value.phone),
  email: /^\S+@\S+\.\S+$/.test(form.value.email) ? '' : 'Informe um e-mail válido',
  password: passwordError(form.value.password, form.value.confirm),
}))
const signupValid = computed(() => Object.values(signupProblems.value).every((p) => !p))

async function signup() {
  if (!signupValid.value) return
  signupError.value = ''
  signing.value = true
  try {
    await api('/auth/register', { method: 'POST', body: {
      name: form.value.name.trim(), phone: form.value.phone, email: form.value.email.trim(),
      password: form.value.password, password_confirm: form.value.confirm } })
    signupDone.value = true
  } catch (e) { signupError.value = e.message }
  finally { signing.value = false }
}

// O botão do Google só aparece se o servidor tiver o login com Google configurado e o script do Google carregar.
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
    <h1 class="page-title">{{ tab === 'login' ? 'Entrar' : 'Criar conta' }}</h1>
    <p class="text-body-medium text-medium-emphasis mt-1 mb-5">
      {{ tab === 'login' ? 'Acesse o painel administrativo.' : 'Preencha seus dados. Você receberá um e-mail para confirmar o cadastro.' }}
    </p>

    <v-tabs v-model="tab" grow class="mb-5" color="primary">
      <v-tab value="login">Entrar</v-tab>
      <v-tab value="signup">Criar conta</v-tab>
    </v-tabs>

    <!-- ENTRAR -->
    <div v-show="tab === 'login'">
      <v-alert v-if="error" :type="needsConfirm ? 'warning' : 'error'" variant="tonal" class="mb-4" density="comfortable">
        {{ error }}
        <div v-if="needsConfirm" class="mt-2">
          <a href="#" class="link" @click.prevent="resend(email)">Reenviar e-mail de confirmação</a>
        </div>
      </v-alert>

      <v-form @submit.prevent="submit">
        <v-text-field v-model="email" label="E-mail" type="email" autocomplete="username" autofocus />
        <v-text-field v-model="password" label="Senha" :type="showPassword ? 'text' : 'password'" autocomplete="current-password"
                      :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                      @click:append-inner="showPassword = !showPassword" />
        <div class="text-right mb-4 mt-n2">
          <router-link :to="{ name: 'forgot' }" class="link">Esqueci minha senha</router-link>
        </div>
        <v-btn type="submit" color="primary" size="x-large" block :loading="loading" :disabled="!email || !password">Entrar</v-btn>
      </v-form>

      <template v-if="googleEnabled">
        <div class="or"><span>ou</span></div>
        <div ref="googleEl" class="google-btn" />
      </template>
    </div>

    <!-- CRIAR CONTA -->
    <div v-show="tab === 'signup'">
      <template v-if="signupDone">
        <v-alert type="success" variant="tonal" class="mb-4" icon="mdi-email-check-outline">
          Enviamos um e-mail para <strong>{{ form.email }}</strong>. Abra o link para confirmar o cadastro (vale 24 horas).
          Depois, o dono da barbearia precisa liberar o seu acesso. Confira também a caixa de spam.
          Se este e-mail já tinha uma conta, a mensagem avisa e explica como entrar (não há link de confirmação).
        </v-alert>
        <a href="#" class="link" @click.prevent="resend(form.email)">Não chegou? Reenviar e-mail</a>
      </template>

      <template v-else>
        <v-alert v-if="signupError" type="error" variant="tonal" class="mb-4" density="comfortable" :text="signupError" />
        <v-form @submit.prevent="signup">
          <v-text-field v-model="form.name" label="Nome" autocomplete="name" />
          <v-text-field v-model="form.phone" label="Celular (WhatsApp)" inputmode="tel" autocomplete="tel"
                        :error-messages="form.phone && signupProblems.phone ? signupProblems.phone : ''" />
          <v-text-field v-model="form.email" label="E-mail" type="email" autocomplete="email"
                        :error-messages="form.email && signupProblems.email ? signupProblems.email : ''" />
          <v-text-field v-model="form.password" label="Senha (mínimo 10 caracteres)" :type="showSignupPassword ? 'text' : 'password'"
                        autocomplete="new-password" :append-inner-icon="showSignupPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                        @click:append-inner="showSignupPassword = !showSignupPassword" />
          <v-text-field v-model="form.confirm" label="Repita a senha" :type="showSignupPassword ? 'text' : 'password'" autocomplete="new-password"
                        :error-messages="form.confirm && signupProblems.password ? signupProblems.password : ''" />
          <p class="privacy">
            Por segurança, registramos o seu endereço IP e a sua localização aproximada ao criar a conta,
            e o dono da barbearia recebe o seu nome, celular e localização para decidir sobre o acesso.
          </p>
          <v-btn type="submit" color="primary" size="x-large" block :loading="signing" :disabled="!signupValid">Criar conta</v-btn>
        </v-form>
      </template>
    </div>
  </AuthShell>
</template>

<style scoped>
.privacy { font-size: 0.78rem; line-height: 1.45; color: rgba(var(--v-theme-on-surface), 0.62); margin: 2px 0 14px; }
.google-btn { min-height: 44px; display: flex; justify-content: center; }
.or { display: flex; align-items: center; gap: 12px; margin: 18px 0; font-size: 0.8rem; color: rgba(var(--v-theme-on-surface), 0.55); }
.or::before, .or::after { content: ''; flex: 1; height: 1px; background: rgba(var(--v-theme-on-surface), 0.12); }
.link { font-size: 0.85rem; color: #8a6420; text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
