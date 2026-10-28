<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import AuthShell from '../components/AuthShell.vue'
import { passwordError } from '../utils/password'

const route = useRoute()
const token = computed(() => String(route.query.token ?? ''))

const password = ref('')
const confirm = ref('')
const show = ref(false)
const loading = ref(false)
const error = ref('')
const done = ref(false)
const invalidLink = ref(!token.value)

const problem = computed(() => passwordError(password.value, confirm.value))

async function submit() {
  if (problem.value) return
  error.value = ''
  loading.value = true
  try {
    await api('/auth/reset-password', { method: 'POST', body: { token: token.value, new_password: password.value } })
    done.value = true
  } catch (e) {
    if (e.status === 400) invalidLink.value = true   // link expirado, já usado ou inválido
    else error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell>
    <h1 class="page-title">Nova senha</h1>

    <template v-if="done">
      <v-alert type="success" variant="tonal" class="mt-4 mb-4" icon="mdi-check-circle-outline">
        Senha alterada com sucesso. Use a nova senha para entrar.
      </v-alert>
      <v-btn color="primary" size="x-large" block :to="{ name: 'login' }">Ir para o login</v-btn>
    </template>

    <template v-else-if="invalidLink">
      <v-alert type="error" variant="tonal" class="mt-4 mb-4" icon="mdi-link-off">
        Este link é inválido ou expirou. Cada link vale por 30 minutos e só pode ser usado uma vez.
      </v-alert>
      <v-btn color="primary" size="x-large" block :to="{ name: 'forgot' }">Pedir um novo link</v-btn>
    </template>

    <template v-else>
      <p class="text-body-medium text-medium-emphasis mt-1 mb-6">Escolha uma nova senha para o painel (mínimo de 10 caracteres).</p>
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="comfortable" :text="error" />
      <v-form @submit.prevent="submit">
        <v-text-field v-model="password" label="Nova senha" :type="show ? 'text' : 'password'" autocomplete="new-password" autofocus
                      :append-inner-icon="show ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" @click:append-inner="show = !show" />
        <v-text-field v-model="confirm" label="Repita a nova senha" :type="show ? 'text' : 'password'" autocomplete="new-password"
                      :error-messages="confirm && problem ? problem : ''" />
        <v-btn class="mt-2" type="submit" color="primary" size="x-large" block :loading="loading" :disabled="!!problem">Salvar nova senha</v-btn>
      </v-form>
    </template>
  </AuthShell>
</template>
