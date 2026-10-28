<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { formatPhone } from '../utils/format'
import { formatDateTime } from '../utils/datetime'
import { notify, notifyError } from '../utils/notify'
import StatusChip from '../components/StatusChip.vue'

const PAGE = 20
const clients = ref([])
const loading = ref(false)
const search = ref('')
const page = ref(0)
const hasNext = ref(false)

let timer
async function load() {
  loading.value = true
  try {
    // Pede um a mais para saber se existe próxima página.
    const rows = await api('/clients', { params: { q: search.value.trim(), limit: PAGE + 1, offset: page.value * PAGE } })
    hasNext.value = rows.length > PAGE
    clients.value = rows.slice(0, PAGE)
  } catch (e) { notifyError(e) }
  finally { loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))
watch(search, () => { clearTimeout(timer); timer = setTimeout(() => { page.value = 0; load() }, 300) })
const go = (delta) => { page.value += delta; load() }

// ---- criar / editar ----
const dialog = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = ref({ name: '', phone: '' })
const digits = (v) => (v ?? '').replace(/\D/g, '')
const phoneOk = (v) => [10, 11, 12, 13].includes(digits(v).length) || 'Informe DDD + número (ex.: 11 99999-8888)'

function openNew() { editingId.value = null; form.value = { name: '', phone: '' }; dialog.value = true }
function openEdit(c) { editingId.value = c.id; form.value = { name: c.name, phone: formatPhone(c.phone) }; dialog.value = true }

async function save() {
  saving.value = true
  const body = { name: form.value.name.trim(), phone: form.value.phone }
  try {
    if (editingId.value) await api(`/clients/${editingId.value}`, { method: 'PATCH', body })
    else await api('/clients', { method: 'POST', body })
    notify(editingId.value ? 'Cliente atualizado' : 'Cliente cadastrado')
    dialog.value = false
    await load()
  } catch (e) { notifyError(e) }  // ex.: 409 "Já existe um cliente com este telefone"
  finally { saving.value = false }
}

// ---- histórico ----
const history = ref(null)
const historyRows = ref([])
async function openHistory(c) {
  history.value = c
  historyRows.value = []
  try { historyRows.value = await api(`/clients/${c.id}/appointments`) } catch (e) { notifyError(e) }
}
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-4">
    <h1 class="text-headline-small mr-auto">Clientes</h1>
    <v-text-field v-model="search" placeholder="Buscar por nome ou telefone" prepend-inner-icon="mdi-magnify"
                  clearable hide-details density="compact" style="max-width: 300px" />
    <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">Novo cliente</v-btn>
  </div>

  <v-card>
    <v-progress-linear v-if="loading" indeterminate />
    <v-list v-if="clients.length" lines="one">
      <v-list-item v-for="c in clients" :key="c.id" :title="c.name" :subtitle="formatPhone(c.phone)">
        <template #append>
          <v-btn icon="mdi-history" variant="text" size="small" title="Agendamentos" @click="openHistory(c)" />
          <v-btn icon="mdi-pencil-outline" variant="text" size="small" title="Editar" @click="openEdit(c)" />
        </template>
      </v-list-item>
    </v-list>
    <div v-else-if="!loading" class="pa-8 text-center text-medium-emphasis">
      {{ search ? 'Nenhum cliente encontrado.' : 'Nenhum cliente cadastrado ainda.' }}
    </div>
    <v-divider />
    <div class="d-flex align-center pa-2">
      <v-btn variant="text" prepend-icon="mdi-chevron-left" :disabled="page === 0" @click="go(-1)">Anterior</v-btn>
      <v-spacer /><span class="text-body-small text-medium-emphasis">Página {{ page + 1 }}</span><v-spacer />
      <v-btn variant="text" append-icon="mdi-chevron-right" :disabled="!hasNext" @click="go(1)">Próxima</v-btn>
    </div>
  </v-card>

  <v-dialog v-model="dialog" max-width="440">
    <v-card :title="editingId ? 'Editar cliente' : 'Novo cliente'" class="pa-2">
      <v-card-text>
        <v-text-field v-model="form.name" label="Nome" :rules="[(v) => !!v?.trim() || 'Informe o nome']" autofocus />
        <v-text-field v-model="form.phone" label="Telefone (WhatsApp)" :rules="[phoneOk]" inputmode="tel" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="dialog = false">Cancelar</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving"
               :disabled="!form.name?.trim() || phoneOk(form.phone) !== true" @click="save">Salvar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog :model-value="!!history" max-width="560" @update:model-value="history = null">
    <v-card :title="`Agendamentos de ${history?.name}`" class="pa-2">
      <v-card-text>
        <v-list v-if="historyRows.length" density="compact">
          <v-list-item v-for="a in historyRows" :key="a.id" :title="`${formatDateTime(a.starts_at)} · ${a.service_name}`">
            <template #append><StatusChip :status="a.status" /></template>
          </v-list-item>
        </v-list>
        <div v-else class="text-medium-emphasis">Nenhum agendamento.</div>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn @click="history = null">Fechar</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>
