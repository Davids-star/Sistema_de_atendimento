<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { session } from '../session'
import { formatPhone } from '../utils/format'
import { formatDateTime } from '../utils/datetime'
import { notify, notifyError } from '../utils/notify'

const FILTERS = [
  { value: 'pending_approval', title: 'Aguardando liberação' },
  { value: 'active', title: 'Com acesso' },
  { value: 'pending_email', title: 'E-mail não confirmado' },
  { value: 'disabled', title: 'Desativados' },
]
const STATUS = {
  pending_approval: { label: 'Aguardando liberação', color: 'warning' },
  active: { label: 'Com acesso', color: 'success' },
  pending_email: { label: 'E-mail não confirmado', color: undefined },
  disabled: { label: 'Desativado', color: 'error' },
}

const users = ref([])
const loading = ref(false)
const filter = ref('pending_approval')
const busy = ref(null)

const count = (s) => users.value.filter((u) => u.status === s).length
const shown = computed(() => users.value.filter((u) => u.status === filter.value))
const myId = computed(() => session.user?.id)

async function load() {
  loading.value = true
  try {
    users.value = await api('/users')
    // Se não há ninguém esperando, abre direto em quem tem acesso.
    if (!count('pending_approval') && filter.value === 'pending_approval') filter.value = 'active'
  } catch (e) { notifyError(e) }
  finally { loading.value = false }
}
onMounted(load)

async function act(user, action, okMessage) {
  busy.value = user.id
  try {
    await api(`/users/${user.id}/${action}`, { method: 'POST' })
    notify(okMessage)
    await load()
  } catch (e) { notifyError(e) }
  finally { busy.value = null; toDeactivate.value = null }
}

const toDeactivate = ref(null)
</script>

<template>
  <div class="mb-6">
    <div class="eyebrow mb-1">Acesso</div>
    <h1 class="page-title">Usuários</h1>
    <p class="text-body-medium text-medium-emphasis mt-1">
      Quem cria uma conta só entra no painel depois que você libera o acesso aqui.
    </p>
  </div>

  <v-chip-group v-model="filter" mandatory selected-class="text-primary" class="mb-4">
    <v-chip v-for="f in FILTERS" :key="f.value" :value="f.value" filter variant="outlined">
      {{ f.title }}<span class="count">{{ count(f.value) }}</span>
    </v-chip>
  </v-chip-group>

  <v-progress-linear v-if="loading" indeterminate class="mb-3" rounded />

  <div v-if="!shown.length && !loading" class="empty">Ninguém nesta lista.</div>

  <v-card v-for="u in shown" :key="u.id" class="user mb-3">
    <div class="avatar-initial">{{ u.name.trim().charAt(0).toUpperCase() }}</div>
    <div class="info">
      <div class="d-flex flex-wrap align-center ga-2">
        <span class="name">{{ u.name }}</span>
        <v-chip size="small" variant="tonal" :color="STATUS[u.status].color">{{ STATUS[u.status].label }}</v-chip>
        <v-chip v-if="u.is_owner" size="small" variant="tonal" color="secondary">Dono</v-chip>
        <v-chip v-if="u.id === myId" size="small" variant="outlined">Você</v-chip>
      </div>
      <div class="meta">{{ u.email }}</div>
      <div class="meta num">{{ u.phone ? formatPhone(u.phone) : 'Celular ainda não informado' }} · cadastro em {{ formatDateTime(u.created_at) }}</div>
    </div>
    <div class="actions">
      <v-btn v-if="u.status === 'pending_approval'" color="success" variant="flat" size="small" prepend-icon="mdi-check"
             :loading="busy === u.id" @click="act(u, 'approve', 'Acesso liberado')">Liberar acesso</v-btn>
      <v-btn v-if="u.status === 'active' && !u.is_owner && u.id !== myId" color="error" variant="text" size="small"
             prepend-icon="mdi-account-off-outline" @click="toDeactivate = u">Desativar</v-btn>
      <v-btn v-if="u.status === 'disabled'" variant="tonal" size="small" prepend-icon="mdi-account-reactivate-outline"
             :loading="busy === u.id" @click="act(u, 'reactivate', 'Usuário reativado')">Reativar</v-btn>
    </div>
  </v-card>

  <v-dialog :model-value="!!toDeactivate" max-width="440" @update:model-value="toDeactivate = null">
    <v-card v-if="toDeactivate" title="Desativar usuário?" class="pa-2">
      <v-card-text>
        <strong>{{ toDeactivate.name }}</strong> perde o acesso imediatamente e é desconectado de todos os aparelhos.
        Você pode reativar depois.
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="toDeactivate = null">Voltar</v-btn>
        <v-btn color="error" variant="flat" :loading="busy === toDeactivate.id"
               @click="act(toDeactivate, 'deactivate', 'Usuário desativado')">Desativar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.count { margin-left: 8px; font-weight: 600; opacity: 0.7; }
.user { display: flex; align-items: center; gap: 16px; padding: 16px 18px; flex-wrap: wrap; }
.info { flex: 1; min-width: 220px; }
.name { font-weight: 600; font-size: 1.02rem; }
.meta { font-size: 0.85rem; opacity: 0.7; margin-top: 2px; }
.actions { display: flex; gap: 8px; }
.empty { text-align: center; padding: 48px 16px; opacity: 0.65; }
</style>
