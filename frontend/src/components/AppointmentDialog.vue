<script setup>
// Criar (appointment = null) ou remarcar/editar um agendamento.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { api } from '../api'
import { buildCreateBody, buildUpdateBody, isCreateValid, warningsText } from '../utils/appointments'
import { dayOf, isoToLocalInput, localInputToISO, timeOf, todayISO } from '../utils/datetime'
import { formatBRL, formatDuration, formatPhone } from '../utils/format'
import { notify, notifyError } from '../utils/notify'

const props = defineProps({
  modelValue: Boolean,
  appointment: { type: Object, default: null },   // null = novo
  initialDay: { type: String, default: () => todayISO() },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const editing = computed(() => !!props.appointment)
const services = ref([])
const saving = ref(false)

const form = ref(blank())
function blank() {
  return { mode: 'existing', client: null, phone: '', name: '', serviceId: null, day: props.initialDay,
           startsAt: '', manual: false, manualValue: '', notes: '', status: 'confirmed' }
}

// ---- cliente: busca no servidor enquanto digita ----
const clientItems = ref([])
const clientSearch = ref('')
let clientTimer
watch(clientSearch, (q) => {
  clearTimeout(clientTimer)
  clientTimer = setTimeout(async () => {
    try {
      const rows = await api('/clients', { params: { q, limit: 15 } })
      clientItems.value = rows.map((c) => ({ ...c, label: `${c.name} · ${formatPhone(c.phone)}` }))
    } catch { /* a busca é só uma ajuda; o erro real aparece ao salvar */ }
  }, 250)
})
onBeforeUnmount(() => clearTimeout(clientTimer))

// ---- horários livres ----
const slots = ref([])
const slotsLoading = ref(false)
const service = computed(() => services.value.find((s) => s.id === form.value.serviceId))

async function loadSlots() {
  slots.value = []
  const { serviceId, day } = form.value
  if (!serviceId || !day) return
  slotsLoading.value = true
  try { slots.value = (await api('/availability', { params: { date: day, service_id: serviceId } })).slots }
  catch (e) { notifyError(e) }
  finally { slotsLoading.value = false }
}
watch(() => [form.value.serviceId, form.value.day], () => {
  // Trocou serviço/dia: o horário escolhido antes pode não valer mais (exceto o horário atual, ao editar).
  const keep = editing.value && form.value.startsAt === props.appointment.starts_at
  if (!keep) form.value.startsAt = ''
  loadSlots()
})
watch(() => form.value.manualValue, (v) => { if (form.value.manual) form.value.startsAt = v ? localInputToISO(v) : '' })
watch(() => form.value.manual, (on) => {
  if (on) form.value.manualValue = form.value.startsAt ? isoToLocalInput(form.value.startsAt) : ''
  else form.value.startsAt = ''
})

// ---- abrir: carrega serviços e preenche o formulário ----
watch(() => props.modelValue, async (open) => {
  if (!open) return
  slots.value = []
  clientItems.value = []
  if (!services.value.length) {
    try { services.value = await api('/services') } catch (e) { notifyError(e) }
  }
  const a = props.appointment
  form.value = a
    ? { ...blank(), client: { id: a.client_id, name: a.client_name, phone: a.client_phone }, serviceId: a.service_id,
        day: dayOf(a.starts_at), startsAt: a.starts_at, notes: a.notes ?? '' }
    : blank()
  loadSlots()
}, { immediate: true })   // também funciona se o diálogo já nascer aberto

const valid = computed(() => (editing.value ? !!form.value.serviceId && !!form.value.startsAt : isCreateValid(form.value)))

async function save() {
  saving.value = true
  try {
    let result
    if (editing.value) {
      const body = buildUpdateBody(props.appointment, form.value)
      if (!Object.keys(body).length) { emit('update:modelValue', false); return }
      result = await api(`/appointments/${props.appointment.id}`, { method: 'PATCH', body })
    } else {
      result = await api('/appointments', { method: 'POST', body: buildCreateBody(form.value) })
    }
    const warn = warningsText(result.warnings)
    notify(warn || (editing.value ? 'Agendamento atualizado' : 'Agendamento criado'), warn ? 'warning' : 'success')
    emit('saved')
    emit('update:modelValue', false)
  } catch (e) { notifyError(e) }   // ex.: 409 "Esse horário já está ocupado"
  finally { saving.value = false }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="560" scrollable @update:model-value="emit('update:modelValue', $event)">
    <v-card :title="editing ? 'Editar agendamento' : 'Novo agendamento'">
      <v-card-text class="pt-2">
        <!-- Cliente -->
        <template v-if="editing">
          <div class="mb-4"><div class="text-body-small text-medium-emphasis">Cliente</div>
            <div class="font-weight-medium">{{ form.client?.name }} · {{ formatPhone(form.client?.phone) }}</div></div>
        </template>
        <template v-else>
          <v-btn-toggle v-model="form.mode" mandatory density="compact" variant="outlined" color="primary" divided class="mb-3">
            <v-btn value="existing" size="small">Cliente cadastrado</v-btn>
            <v-btn value="new" size="small">Novo cliente</v-btn>
          </v-btn-toggle>
          <v-autocomplete v-if="form.mode === 'existing'" v-model="form.client" v-model:search="clientSearch"
                          :items="clientItems" item-title="label" return-object no-filter label="Cliente"
                          placeholder="Digite o nome ou telefone" no-data-text="Nenhum cliente encontrado"
                          prepend-inner-icon="mdi-account-search-outline" />
          <template v-else>
            <v-text-field v-model="form.name" label="Nome do cliente" />
            <v-text-field v-model="form.phone" label="Telefone (WhatsApp)" inputmode="tel" hint="DDD + número" persistent-hint class="mb-3" />
          </template>
        </template>

        <!-- Serviço e dia -->
        <v-select v-model="form.serviceId" :items="services" item-value="id" label="Serviço" no-data-text="Cadastre um serviço primeiro">
          <template #item="{ props: p, item }">
            <v-list-item v-bind="p" :title="item.name"
                         :subtitle="`${formatDuration(item.duration_minutes)} · ${formatBRL(item.price_cents)}`" />
          </template>
          <template #selection="{ item }">{{ item.name }} · {{ formatDuration(item.duration_minutes) }} · {{ formatBRL(item.price_cents) }}</template>
        </v-select>
        <v-text-field v-model="form.day" label="Dia" type="date" :min="todayISO()" />

        <!-- Horários -->
        <div class="text-body-medium mb-2">Horário</div>
        <v-progress-linear v-if="slotsLoading" indeterminate class="mb-2" />
        <div v-if="!form.manual" class="d-flex flex-wrap ga-2 mb-2">
          <v-chip v-if="editing && dayOf(appointment.starts_at) === form.day && !slots.some((s) => s === appointment.starts_at)"
                  :color="form.startsAt === appointment.starts_at ? 'primary' : undefined"
                  :variant="form.startsAt === appointment.starts_at ? 'flat' : 'outlined'" @click="form.startsAt = appointment.starts_at">
            {{ timeOf(appointment.starts_at) }} (atual)
          </v-chip>
          <v-chip v-for="s in slots" :key="s" :color="form.startsAt === s ? 'primary' : undefined"
                  :variant="form.startsAt === s ? 'flat' : 'outlined'" @click="form.startsAt = s">{{ timeOf(s) }}</v-chip>
          <span v-if="!slots.length && !slotsLoading" class="text-body-medium text-medium-emphasis">
            {{ form.serviceId ? 'Sem horários livres neste dia.' : 'Escolha o serviço para ver os horários livres.' }}
          </span>
        </div>
        <v-switch v-model="form.manual" label="Escolher outro horário (fora da grade ou do expediente)" density="compact" hide-details color="primary" />
        <v-text-field v-if="form.manual" v-model="form.manualValue" type="datetime-local" label="Data e hora" class="mt-2"
                      hint="Você será avisado se estiver fora do expediente. Horários que já passaram não são aceitos." persistent-hint />

        <v-textarea v-model="form.notes" label="Observações (opcional)" rows="2" auto-grow class="mt-4" />
        <v-select v-if="!editing" v-model="form.status" label="Situação inicial"
                  :items="[{ title: 'Confirmado', value: 'confirmed' }, { title: 'Pendente (aguardando confirmação)', value: 'pending' }]" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="emit('update:modelValue', false)">Cancelar</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" :disabled="!valid" @click="save">
          {{ editing ? 'Salvar alterações' : 'Agendar' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
