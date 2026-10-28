<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { flattenDays, groupByWeekday, validateIntervals, WEEKDAYS } from '../utils/hours'
import { formatDateTime, isoToLocalInput, localInputToISO } from '../utils/datetime'
import { notify, notifyError } from '../utils/notify'

// ---------- intervalo dos horários ----------
const interval = ref(30)
const intervalSaving = ref(false)
const INTERVAL_PRESETS = [15, 20, 30, 45, 60]
const intervalOk = computed(() => Number.isInteger(+interval.value) && +interval.value >= 5 && +interval.value <= 240)

async function saveInterval() {
  intervalSaving.value = true
  try {
    const r = await api('/settings', { method: 'PUT', body: { slot_interval_minutes: +interval.value } })
    interval.value = r.slot_interval_minutes
    notify('Intervalo salvo')
  } catch (e) { notifyError(e) }
  finally { intervalSaving.value = false }
}

// ---------- horário de funcionamento ----------
const days = ref(groupByWeekday([]))
const hoursSaving = ref(false)
const dayErrors = computed(() => Object.fromEntries(Object.entries(days.value).map(([d, list]) => [d, validateIntervals(list)])))
const hoursOk = computed(() => Object.values(dayErrors.value).every((e) => !e))

const addInterval = (d) => days.value[d].push({ start: '09:00', end: '18:00' })
const removeInterval = (d, i) => days.value[d].splice(i, 1)

async function saveHours() {
  if (!hoursOk.value) return
  hoursSaving.value = true
  try {
    const saved = await api('/business-hours', { method: 'PUT', body: { items: flattenDays(days.value) } })
    days.value = groupByWeekday(saved)
    notify('Horário de funcionamento salvo')
  } catch (e) { notifyError(e) }
  finally { hoursSaving.value = false }
}

// ---------- bloqueios ----------
const blocks = ref([])
const blockForm = ref({ starts: '', ends: '', reason: '' })
const blockSaving = ref(false)
const blockError = computed(() => {
  const { starts, ends } = blockForm.value
  if (!starts || !ends) return ''
  return ends <= starts ? 'O fim deve ser depois do início.' : ''
})
const blockOk = computed(() => blockForm.value.starts && blockForm.value.ends && !blockError.value)

async function loadBlocks() {
  try { blocks.value = await api('/blocked-times', { params: { from: new Date().toISOString() } }) }
  catch (e) { notifyError(e) }
}

async function addBlock() {
  blockSaving.value = true
  try {
    await api('/blocked-times', { method: 'POST', body: {
      starts_at: localInputToISO(blockForm.value.starts), ends_at: localInputToISO(blockForm.value.ends),
      reason: blockForm.value.reason?.trim() || null } })
    blockForm.value = { starts: '', ends: '', reason: '' }
    notify('Horário bloqueado')
    await loadBlocks()
  } catch (e) { notifyError(e) }
  finally { blockSaving.value = false }
}

async function removeBlock(b) {
  try { await api(`/blocked-times/${b.id}`, { method: 'DELETE' }); notify('Bloqueio removido'); await loadBlocks() }
  catch (e) { notifyError(e) }
}

onMounted(async () => {
  try {
    const [s, hours] = await Promise.all([api('/settings'), api('/business-hours')])
    interval.value = s.slot_interval_minutes
    days.value = groupByWeekday(hours)
  } catch (e) { notifyError(e) }
  loadBlocks()
})
</script>

<template>
  <h1 class="text-headline-small mb-4">Configurações</h1>

  <v-card class="pa-4 mb-4">
    <div class="text-title-medium">Intervalo entre horários</div>
    <p class="text-body-medium text-medium-emphasis mb-3">
      De quanto em quanto tempo começam os horários oferecidos ao cliente (ex.: 30 min → 9:00, 9:30, 10:00…).
    </p>
    <div class="d-flex flex-wrap align-center ga-3">
      <v-btn-toggle :model-value="+interval" density="comfortable" variant="outlined" color="primary" divided
                    @update:model-value="(v) => v && (interval = v)">
        <v-btn v-for="m in INTERVAL_PRESETS" :key="m" :value="m" size="small">{{ m }} min</v-btn>
      </v-btn-toggle>
      <v-text-field v-model="interval" label="Outro valor (min)" type="number" hide-details density="compact"
                    style="max-width: 170px" :error="!intervalOk" />
      <v-btn color="primary" :loading="intervalSaving" :disabled="!intervalOk" @click="saveInterval">Salvar</v-btn>
    </div>
  </v-card>

  <v-card class="pa-4 mb-4">
    <div class="text-title-medium">Horário de funcionamento</div>
    <p class="text-body-medium text-medium-emphasis mb-3">
      Um dia sem horário fica fechado. Use mais de um intervalo para marcar uma pausa (ex.: 9h–12h e 14h–18h).
    </p>
    <div v-for="(name, d) in WEEKDAYS" :key="d" class="day-row">
      <div class="day-name">{{ name }}</div>
      <div class="flex-grow-1">
        <div v-if="!days[d].length" class="text-medium-emphasis pt-2">Fechado</div>
        <div v-for="(iv, i) in days[d]" :key="i" class="d-flex align-center ga-2 mb-1">
          <v-text-field v-model="iv.start" type="time" hide-details density="compact" style="max-width: 140px" aria-label="Início" />
          <span>até</span>
          <v-text-field v-model="iv.end" type="time" hide-details density="compact" style="max-width: 140px" aria-label="Fim" />
          <v-btn icon="mdi-close" variant="text" size="small" title="Remover intervalo" @click="removeInterval(d, i)" />
        </div>
        <div v-if="dayErrors[d]" class="text-error text-body-small">{{ dayErrors[d] }}</div>
      </div>
      <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addInterval(d)">Intervalo</v-btn>
    </div>
    <div class="d-flex justify-end mt-3">
      <v-btn color="primary" :loading="hoursSaving" :disabled="!hoursOk" @click="saveHours">Salvar horários</v-btn>
    </div>
  </v-card>

  <v-card class="pa-4">
    <div class="text-title-medium">Bloqueios</div>
    <p class="text-body-medium text-medium-emphasis mb-3">
      Períodos em que não se atende (folga, médico, feriado). Não aparecem como disponíveis para o cliente.
    </p>
    <v-row dense>
      <v-col cols="12" sm="4"><v-text-field v-model="blockForm.starts" label="Início" type="datetime-local" hide-details="auto" /></v-col>
      <v-col cols="12" sm="4"><v-text-field v-model="blockForm.ends" label="Fim" type="datetime-local" :error-messages="blockError" hide-details="auto" /></v-col>
      <v-col cols="12" sm="4"><v-text-field v-model="blockForm.reason" label="Motivo (opcional)" hide-details="auto" /></v-col>
    </v-row>
    <v-btn class="mt-3" color="primary" prepend-icon="mdi-lock-outline" :loading="blockSaving" :disabled="!blockOk"
           @click="addBlock">Bloquear</v-btn>

    <v-list v-if="blocks.length" class="mt-4" density="compact">
      <v-list-item v-for="b in blocks" :key="b.id" :title="`${formatDateTime(b.starts_at)} → ${formatDateTime(b.ends_at)}`"
                   :subtitle="b.reason || 'Sem motivo informado'">
        <template #append><v-btn icon="mdi-delete-outline" variant="text" size="small" color="error" title="Remover" @click="removeBlock(b)" /></template>
      </v-list-item>
    </v-list>
    <div v-else class="mt-4 text-medium-emphasis">Nenhum bloqueio futuro.</div>
  </v-card>
</template>

<style scoped>
.day-row { display: flex; align-items: flex-start; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.day-name { width: 120px; padding-top: 8px; font-weight: 500; flex-shrink: 0; }
@media (max-width: 600px) { .day-row { flex-wrap: wrap; } .day-name { width: 100%; padding-top: 0; } }
</style>
