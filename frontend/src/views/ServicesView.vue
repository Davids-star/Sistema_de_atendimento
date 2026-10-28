<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { centsToInput, formatBRL, formatDuration, parseBRL } from '../utils/format'
import { notify, notifyError } from '../utils/notify'

const headers = [
  { title: 'Serviço', key: 'name' },
  { title: 'Duração', key: 'duration_minutes' },
  { title: 'Preço', key: 'price_cents' },
  { title: 'Situação', key: 'is_active' },
  { title: 'Ações', key: 'actions', sortable: false, align: 'end' },
]

const services = ref([])
const loading = ref(false)
const showInactive = ref(true)

async function load() {
  loading.value = true
  try { services.value = await api('/services', { params: { include_inactive: true } }) }
  catch (e) { notifyError(e) }
  finally { loading.value = false }
}
onMounted(load)

const items = computed(() => services.value.filter((s) => showInactive.value || s.is_active))

// ---- criar / editar ----
const dialog = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = ref({ name: '', description: '', price: '', duration: 30 })

const priceCents = computed(() => parseBRL(form.value.price))
const rules = {
  name: [(v) => !!v?.trim() || 'Informe o nome'],
  price: [(v) => parseBRL(v) !== null || 'Valor inválido (ex.: 40,00)'],
  duration: [(v) => (Number.isInteger(+v) && +v > 0 && +v <= 480) || 'Entre 1 e 480 minutos'],
}
const formValid = computed(() =>
  !!form.value.name?.trim() && priceCents.value !== null && Number.isInteger(+form.value.duration)
  && +form.value.duration > 0 && +form.value.duration <= 480)

function openNew() {
  editingId.value = null
  form.value = { name: '', description: '', price: '', duration: 30 }
  dialog.value = true
}
function openEdit(s) {
  editingId.value = s.id
  form.value = { name: s.name, description: s.description ?? '', price: centsToInput(s.price_cents), duration: s.duration_minutes }
  dialog.value = true
}

async function save() {
  if (!formValid.value) return
  saving.value = true
  const body = {
    name: form.value.name.trim(),
    description: form.value.description?.trim() || null,
    price_cents: priceCents.value,
    duration_minutes: +form.value.duration,
  }
  try {
    if (editingId.value) await api(`/services/${editingId.value}`, { method: 'PATCH', body })
    else await api('/services', { method: 'POST', body })
    notify(editingId.value ? 'Serviço atualizado' : 'Serviço criado')
    dialog.value = false
    await load()
  } catch (e) { notifyError(e) }
  finally { saving.value = false }
}

async function toggleActive(s) {
  try {
    await api(`/services/${s.id}`, { method: 'PATCH', body: { is_active: !s.is_active } })
    notify(s.is_active ? 'Serviço desativado' : 'Serviço reativado')
    await load()
  } catch (e) { notifyError(e) }
}

// ---- excluir ----
const toDelete = ref(null)
async function confirmDelete() {
  const s = toDelete.value
  try {
    await api(`/services/${s.id}`, { method: 'DELETE' })
    await load()
    // Se o serviço já foi usado em agendamentos a API só desativa; avisamos o que realmente aconteceu.
    notify(services.value.some((x) => x.id === s.id) ? 'Serviço já usado em agendamentos: foi apenas desativado' : 'Serviço excluído')
  } catch (e) { notifyError(e) }
  toDelete.value = null
}
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-6">
    <div class="mr-auto"><div class="eyebrow mb-1">Catálogo</div><h1 class="page-title">Serviços</h1></div>
    <v-switch v-model="showInactive" label="Mostrar inativos" hide-details density="compact" color="primary" />
    <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">Novo serviço</v-btn>
  </div>

  <v-card>
    <v-data-table :headers="headers" :items="items" :loading="loading" hide-default-footer
                  items-per-page="-1" no-data-text="Nenhum serviço cadastrado.">
      <template #item.name="{ item }">
        <div class="font-weight-medium">{{ item.name }}</div>
        <div v-if="item.description" class="text-body-small text-medium-emphasis">{{ item.description }}</div>
      </template>
      <template #item.duration_minutes="{ item }">{{ formatDuration(item.duration_minutes) }}</template>
      <template #item.price_cents="{ item }">{{ formatBRL(item.price_cents) }}</template>
      <template #item.is_active="{ item }">
        <v-chip :color="item.is_active ? 'success' : undefined" size="small" variant="tonal">
          {{ item.is_active ? 'Ativo' : 'Inativo' }}
        </v-chip>
      </template>
      <template #item.actions="{ item }">
        <v-btn icon="mdi-pencil-outline" variant="text" size="small" title="Editar" @click="openEdit(item)" />
        <v-btn :icon="item.is_active ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" variant="text" size="small"
               :title="item.is_active ? 'Desativar' : 'Reativar'" @click="toggleActive(item)" />
        <v-btn icon="mdi-delete-outline" variant="text" size="small" color="error" title="Excluir" @click="toDelete = item" />
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="480">
    <v-card :title="editingId ? 'Editar serviço' : 'Novo serviço'" class="pa-2">
      <v-card-text>
        <v-text-field v-model="form.name" label="Nome" :rules="rules.name" autofocus />
        <v-textarea v-model="form.description" label="Descrição (opcional)" rows="2" auto-grow variant="outlined" />
        <v-row>
          <v-col cols="6"><v-text-field v-model="form.price" label="Preço (R$)" :rules="rules.price" inputmode="decimal" /></v-col>
          <v-col cols="6"><v-text-field v-model="form.duration" label="Duração (min)" type="number" :rules="rules.duration" /></v-col>
        </v-row>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="dialog = false">Cancelar</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" :disabled="!formValid" @click="save">Salvar</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog :model-value="!!toDelete" max-width="440" @update:model-value="toDelete = null">
    <v-card title="Excluir serviço?" class="pa-2">
      <v-card-text>
        “{{ toDelete?.name }}” será excluído. Se já tiver sido usado em algum agendamento, ele será
        apenas desativado, para o histórico não se perder.
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="toDelete = null">Voltar</v-btn>
        <v-btn color="error" variant="flat" @click="confirmDelete">Excluir</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
