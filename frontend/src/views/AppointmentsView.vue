<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import AppointmentDialog from '../components/AppointmentDialog.vue'
import StatusChip from '../components/StatusChip.vue'
import { ACTION_LABEL, ACTION_PATH, availableActions, canEdit, CONFIRM_TEXT, NEEDS_CONFIRMATION } from '../utils/appointments'
import { addDays, dayOf, formatDateTime, formatDayLong, startOfWeek, timeOf, todayISO, weekdayShort } from '../utils/datetime'
import { formatBRL, formatPhone } from '../utils/format'
import { notify, notifyError } from '../utils/notify'

const ACTION_ICON = { confirm: 'mdi-check', cancel: 'mdi-close', complete: 'mdi-check-all', no_show: 'mdi-account-off-outline' }
const ACTION_COLOR = { confirm: 'success', cancel: 'error', complete: 'primary', no_show: 'warning' }

const mode = ref('day')          // 'day' = agenda do dia | 'pending' = sem desfecho
const day = ref(todayISO())
const items = ref([])
const week = ref([])             // contagem por dia da semana exibida
const loading = ref(false)

const weekStart = computed(() => startOfWeek(day.value))
const weekDays = computed(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart.value, i)))
const countOf = (d) => week.value.find((x) => x.date === d)?.by_status
const activeCount = (d) => { const c = countOf(d); return c ? c.pending + c.confirmed + c.completed + c.no_show : 0 }

async function load() {
  loading.value = true
  try {
    if (mode.value === 'pending') {
      items.value = await api('/appointments', { params: { needs_outcome: true, limit: 500 } })
    } else {
      const [list, byDay] = await Promise.all([
        api('/appointments', { params: { date_from: day.value, date_to: day.value, limit: 500 } }),
        api('/dashboard/appointments-by-day', { params: { date_from: weekStart.value, date_to: addDays(weekStart.value, 6) } }),
      ])
      items.value = list
      week.value = byDay
    }
  } catch (e) { notifyError(e) }
  finally { loading.value = false }
}
onMounted(load)
watch([mode, day], load)

const shift = (n) => { day.value = addDays(day.value, n) }
const now = () => new Date()
const actionsOf = (a) => availableActions(a, now())

// ---- ações de status ----
const pendingAction = ref(null)   // { appointment, action } aguardando confirmação
const acting = ref(false)

async function runAction(a, action) {
  acting.value = true
  try {
    await api(`/appointments/${a.id}/${ACTION_PATH[action]}`, { method: 'POST' })
    notify({ confirm: 'Agendamento confirmado', cancel: 'Agendamento cancelado', complete: 'Atendimento concluído', no_show: 'Marcado como ausente' }[action])
    await load()
  } catch (e) { notifyError(e); await load() }   // recarrega: o estado pode ter mudado em outra aba
  finally { acting.value = false; pendingAction.value = null }
}
const askOrRun = (a, action) => (NEEDS_CONFIRMATION.has(action) ? (pendingAction.value = { appointment: a, action }) : runAction(a, action))

// ---- criar / editar ----
const dialog = ref(false)
const editing = ref(null)
const openNew = () => { editing.value = null; dialog.value = true }
const openEdit = (a) => { editing.value = a; dialog.value = true }
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-4">
    <h1 class="text-headline-small mr-auto">Agendamentos</h1>
    <v-btn-toggle v-model="mode" mandatory density="comfortable" variant="outlined" color="primary" divided>
      <v-btn value="day" size="small" prepend-icon="mdi-calendar-today">Agenda</v-btn>
      <v-btn value="pending" size="small" prepend-icon="mdi-clock-alert-outline">Sem desfecho</v-btn>
    </v-btn-toggle>
    <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">Novo agendamento</v-btn>
  </div>

  <template v-if="mode === 'day'">
    <v-card class="pa-3 mb-4">
      <div class="d-flex align-center ga-2 mb-3">
        <v-btn icon="mdi-chevron-left" variant="text" title="Dia anterior" @click="shift(-1)" />
        <v-text-field v-model="day" type="date" hide-details density="compact" style="max-width: 190px" aria-label="Dia" />
        <v-btn icon="mdi-chevron-right" variant="text" title="Próximo dia" @click="shift(1)" />
        <v-btn variant="tonal" size="small" :disabled="day === todayISO()" @click="day = todayISO()">Hoje</v-btn>
        <span class="ml-auto text-title-medium d-none d-sm-inline">{{ formatDayLong(day) }}</span>
      </div>
      <div class="week">
        <button v-for="d in weekDays" :key="d" type="button" class="week-day" :class="{ selected: d === day, today: d === todayISO() }"
                @click="day = d">
          <span class="text-body-small">{{ weekdayShort(d) }}</span>
          <span class="text-title-medium">{{ d.slice(8) }}</span>
          <span class="count" :class="{ zero: !activeCount(d) }">{{ activeCount(d) }}</span>
        </button>
      </div>
    </v-card>
  </template>
  <v-alert v-else type="info" variant="tonal" class="mb-4" icon="mdi-information-outline">
    Agendamentos que já terminaram e ainda estão pendentes ou confirmados. Marque cada um como concluído, ausente ou cancele.
  </v-alert>

  <v-progress-linear v-if="loading" indeterminate class="mb-2" />

  <div v-if="!items.length && !loading" class="text-center text-medium-emphasis pa-10">
    {{ mode === 'pending' ? 'Tudo em dia! Nenhum agendamento sem desfecho.' : 'Nenhum agendamento neste dia.' }}
  </div>

  <v-card v-for="a in items" :key="a.id" class="pa-3 mb-2 appt" :class="{ dim: !canEdit(a) }">
    <div class="d-flex flex-wrap align-center ga-3">
      <div class="time">
        <div class="text-title-medium">{{ timeOf(a.starts_at) }}</div>
        <div class="text-body-small text-medium-emphasis">até {{ timeOf(a.ends_at) }}</div>
      </div>
      <div class="flex-grow-1 info">
        <div class="font-weight-medium">{{ a.client_name }}
          <span class="text-body-small text-medium-emphasis ml-1">{{ formatPhone(a.client_phone) }}</span></div>
        <div class="text-body-medium">{{ a.service_name }} · {{ formatBRL(a.price_cents) }}
          <span v-if="mode === 'pending'" class="text-medium-emphasis"> · {{ formatDateTime(a.starts_at) }}</span></div>
        <div v-if="a.notes" class="text-body-small text-medium-emphasis">“{{ a.notes }}”</div>
      </div>
      <StatusChip :status="a.status" />
      <div class="d-flex ga-1">
        <v-btn v-for="act in actionsOf(a)" :key="act" size="small" variant="tonal" :color="ACTION_COLOR[act]"
               :prepend-icon="ACTION_ICON[act]" :disabled="acting" @click="askOrRun(a, act)">{{ ACTION_LABEL[act] }}</v-btn>
        <v-btn v-if="canEdit(a)" icon="mdi-pencil-outline" size="small" variant="text" title="Editar / remarcar" @click="openEdit(a)" />
      </div>
    </div>
  </v-card>

  <AppointmentDialog v-model="dialog" :appointment="editing" :initial-day="day" @saved="load" />

  <v-dialog :model-value="!!pendingAction" max-width="440" @update:model-value="pendingAction = null">
    <v-card v-if="pendingAction" :title="`${ACTION_LABEL[pendingAction.action]}?`" class="pa-2">
      <v-card-text>
        <strong>{{ pendingAction.appointment.client_name }}</strong> · {{ formatDateTime(pendingAction.appointment.starts_at) }}<br />
        {{ CONFIRM_TEXT[pendingAction.action] }}
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="pendingAction = null">Voltar</v-btn>
        <v-btn :color="ACTION_COLOR[pendingAction.action]" variant="flat" :loading="acting"
               @click="runAction(pendingAction.appointment, pendingAction.action)">{{ ACTION_LABEL[pendingAction.action] }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.week { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
.week-day { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 4px; border-radius: 8px;
            border: 1px solid rgba(var(--v-theme-on-surface), 0.12); background: transparent; cursor: pointer; color: inherit; }
.week-day:hover { background: rgba(var(--v-theme-primary), 0.06); }
.week-day.today { border-color: rgb(var(--v-theme-primary)); }
.week-day.selected { background: rgb(var(--v-theme-primary)); color: rgb(var(--v-theme-on-primary)); border-color: rgb(var(--v-theme-primary)); }
.count { font-size: 11px; min-width: 20px; padding: 0 6px; border-radius: 10px; background: rgba(var(--v-theme-secondary), 0.25); }
.week-day.selected .count { background: rgba(255, 255, 255, 0.3); }
.count.zero { opacity: 0.4; }
.time { width: 70px; flex-shrink: 0; }
.info { min-width: 180px; }
.dim { opacity: 0.65; }
</style>
