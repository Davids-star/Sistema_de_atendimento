<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import AppointmentDialog from '../components/AppointmentDialog.vue'
import StatusChip from '../components/StatusChip.vue'
import { ACTION_LABEL, ACTION_PATH, availableActions, canEdit, CONFIRM_TEXT, NEEDS_CONFIRMATION } from '../utils/appointments'
import { addDays, dayOf, formatDateTime, formatDayLong, startOfWeek, timeOf, todayISO, weekdayShort } from '../utils/datetime'
import { formatBRL, formatPhone } from '../utils/format'
import { notify, notifyError } from '../utils/notify'
import { appointmentWhatsappLink } from '../utils/whatsapp'

const ACTION_ICON = { confirm: 'mdi-check', cancel: 'mdi-close', complete: 'mdi-check-all', no_show: 'mdi-account-off-outline' }
const ACTION_COLOR = { confirm: 'success', cancel: 'error', complete: 'primary', no_show: 'warning' }
// Ação principal = botão cheio; as demais ficam discretas.
const ACTION_VARIANT = { confirm: 'flat', complete: 'flat', no_show: 'outlined', cancel: 'text' }

const mode = ref('day')          // 'day' = agenda do dia | 'upcoming' = todos os próximos | 'pending' = sem desfecho
const day = ref(todayISO())
const items = ref([])
const week = ref([])             // contagem por dia da semana exibida
const loading = ref(false)
const next = ref(null)           // próximo agendamento (mostrado quando o dia aberto está vazio)

const weekStart = computed(() => startOfWeek(day.value))
const weekDays = computed(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart.value, i)))
const countOf = (d) => week.value.find((x) => x.date === d)?.by_status
const activeCount = (d) => { const c = countOf(d); return c ? c.pending + c.confirmed + c.completed + c.no_show : 0 }

async function load() {
  loading.value = true
  try {
    if (mode.value === 'pending') {
      items.value = await api('/appointments', { params: { needs_outcome: true, limit: 500 } })
    } else if (mode.value === 'upcoming') {
      items.value = await api('/appointments', { params: { upcoming: true, limit: 200 } })
    } else {
      const [list, byDay] = await Promise.all([
        api('/appointments', { params: { date_from: day.value, date_to: day.value, limit: 500 } }),
        api('/dashboard/appointments-by-day', { params: { date_from: weekStart.value, date_to: addDays(weekStart.value, 6) } }),
      ])
      items.value = list
      week.value = byDay
      // Dia vazio: procura o próximo agendamento para a pessoa não achar que "sumiu tudo".
      next.value = list.length ? null : (await api('/appointments', { params: { upcoming: true, limit: 1 } }))[0] ?? null
    }
  } catch (e) { notifyError(e) }
  finally { loading.value = false }
}
onMounted(load)
watch([mode, day], load)

const shift = (n) => { day.value = addDays(day.value, n) }
// Na lista "Próximos", mostra um título quando muda o dia.
const startsNewDay = (i) => i === 0 || dayOf(items.value[i - 1].starts_at) !== dayOf(items.value[i].starts_at)
function goToNext() {
  day.value = dayOf(next.value.starts_at)
  mode.value = 'day'
}
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
  <div class="d-flex flex-wrap align-center ga-3 mb-6">
    <div class="mr-auto">
      <div class="eyebrow mb-1">{{ mode === 'day' ? formatDayLong(day) : mode === 'upcoming' ? 'Daqui para frente' : 'Pendências' }}</div>
      <h1 class="page-title">Agendamentos</h1>
    </div>
    <v-btn-toggle v-model="mode" mandatory density="comfortable" variant="outlined" color="primary" divided>
      <v-btn value="day" size="small" prepend-icon="mdi-calendar-today">Agenda</v-btn>
      <v-btn value="upcoming" size="small" prepend-icon="mdi-calendar-arrow-right">Próximos</v-btn>
      <v-btn value="pending" size="small" prepend-icon="mdi-clock-alert-outline">Sem desfecho</v-btn>
    </v-btn-toggle>
    <v-btn class="d-none d-sm-flex" color="primary" prepend-icon="mdi-plus" size="large" @click="openNew">Novo agendamento</v-btn>
  </div>

  <template v-if="mode === 'day'">
    <v-card class="pa-4 mb-5">
      <div class="d-flex align-center ga-1 mb-4">
        <v-btn icon="mdi-chevron-left" variant="text" density="comfortable" title="Dia anterior" @click="shift(-1)" />
        <v-text-field v-model="day" type="date" hide-details density="compact" class="day-input" aria-label="Dia" />
        <v-btn icon="mdi-chevron-right" variant="text" density="comfortable" title="Próximo dia" @click="shift(1)" />
        <v-btn class="ml-2" variant="tonal" size="small" :disabled="day === todayISO()" @click="day = todayISO()">Hoje</v-btn>
      </div>
      <div class="week">
        <button v-for="d in weekDays" :key="d" type="button" class="week-day" :class="{ selected: d === day, today: d === todayISO() }"
                @click="day = d">
          <span class="wd">{{ weekdayShort(d) }}</span>
          <span class="dn num">{{ d.slice(8) }}</span>
          <span class="count num" :class="{ zero: !activeCount(d) }">{{ activeCount(d) }}</span>
        </button>
      </div>
    </v-card>
  </template>
  <v-alert v-else-if="mode === 'pending'" type="info" variant="tonal" class="mb-5" icon="mdi-information-outline">
    Agendamentos que já terminaram e ainda estão pendentes ou confirmados. Marque cada um como concluído ou ausente, ou cancele.
  </v-alert>

  <v-progress-linear v-if="loading" indeterminate class="mb-3" rounded />

  <div v-if="!items.length && !loading" class="empty">
    <v-icon :icon="mode === 'pending' ? 'mdi-check-circle-outline' : 'mdi-calendar-blank-outline'" size="44" />
    <div class="mt-2">{{ mode === 'pending' ? 'Tudo em dia! Nenhum agendamento sem desfecho.' : mode === 'upcoming' ? 'Nenhum agendamento marcado daqui para frente.' : 'Nenhum agendamento neste dia.' }}</div>
    <div v-if="mode === 'day' && next" class="next mt-4">
      <div class="text-body-medium">Seu próximo agendamento é <strong>{{ formatDateTime(next.starts_at) }}</strong>
        ({{ next.client_name }} · {{ next.service_name }}).</div>
      <v-btn class="mt-2" color="primary" variant="flat" prepend-icon="mdi-calendar-arrow-right" @click="goToNext">Ver esse dia</v-btn>
    </div>
    <v-btn v-if="mode !== 'pending'" class="mt-4" variant="tonal" prepend-icon="mdi-plus" @click="openNew">Novo agendamento</v-btn>
  </div>

  <template v-for="(a, i) in items" :key="a.id">
  <div v-if="mode === 'upcoming' && startsNewDay(i)" class="day-head">{{ formatDayLong(dayOf(a.starts_at)) }}</div>
  <v-card class="appt mb-3" :class="[`s-${a.status}`, { dim: !canEdit(a) }]">
    <div class="appt-main">
      <div class="time">
        <div class="t1 num">{{ timeOf(a.starts_at) }}</div>
        <div class="t2 num">até {{ timeOf(a.ends_at) }}</div>
      </div>
      <div class="info">
        <div class="d-flex flex-wrap align-center ga-2">
          <a v-if="appointmentWhatsappLink(a)" class="client wa" :href="appointmentWhatsappLink(a)" target="_blank" rel="noopener noreferrer"
             :aria-label="`Conversar com ${a.client_name} no WhatsApp`" :title="'Abrir o WhatsApp com uma mensagem pronta'">
            {{ a.client_name }}<v-icon icon="mdi-whatsapp" size="16" class="wa-icon" />
          </a>
          <span v-else class="client">{{ a.client_name }}</span>
          <StatusChip :status="a.status" />
        </div>
        <div class="service">
          {{ a.service_name }} · <span class="num">{{ formatBRL(a.price_cents) }}</span>
          <span v-if="mode === 'pending'" class="text-medium-emphasis"> · {{ formatDateTime(a.starts_at) }}</span>
        </div>
        <div class="phone num">{{ formatPhone(a.client_phone) }}</div>
        <div v-if="a.notes" class="notes">“{{ a.notes }}”</div>
        <div v-if="a.status === 'cancelled'" class="cancelled-by">
          Cancelado por <strong>{{ a.cancelled_by || 'não informado' }}</strong><span v-if="a.cancelled_at"> · {{ formatDateTime(a.cancelled_at) }}</span>
        </div>
      </div>
    </div>
    <div v-if="actionsOf(a).length || canEdit(a)" class="actions">
      <v-btn v-for="act in actionsOf(a)" :key="act" size="small" :variant="ACTION_VARIANT[act]" :color="ACTION_COLOR[act]"
             :prepend-icon="ACTION_ICON[act]" :disabled="acting" @click="askOrRun(a, act)">{{ ACTION_LABEL[act] }}</v-btn>
      <v-spacer class="d-none d-sm-block" />
      <v-btn v-if="canEdit(a)" class="edit-btn" size="small" variant="text" prepend-icon="mdi-pencil-outline" title="Editar / remarcar" @click="openEdit(a)"><span class="edit-label">Editar</span></v-btn>
    </div>
  </v-card>
  </template>

  <v-btn class="fab d-sm-none" color="primary" icon="mdi-plus" size="large" elevation="6" title="Novo agendamento" @click="openNew" />

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
.day-input { max-width: 180px; }

/* Faixa da semana */
.week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
.week-day { display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 10px 4px 8px; border-radius: 12px;
            border: 1px solid rgba(var(--v-theme-on-surface), 0.1); background: transparent; cursor: pointer; color: inherit;
            transition: background 0.12s, border-color 0.12s; }
.week-day:hover { background: rgba(var(--v-theme-primary), 0.06); }
.week-day .wd { font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.65; }
.week-day .dn { font-size: 1.25rem; font-weight: 600; line-height: 1.1; }
.week-day.today { border-color: rgb(var(--v-theme-secondary)); box-shadow: inset 0 0 0 1px rgb(var(--v-theme-secondary)); }
.week-day.selected { background: rgb(var(--v-theme-primary)); color: rgb(var(--v-theme-on-primary)); border-color: rgb(var(--v-theme-primary)); }
.count { font-size: 11px; font-weight: 600; min-width: 22px; padding: 1px 6px; border-radius: 10px; background: rgba(var(--v-theme-secondary), 0.2); }
.week-day.selected .count { background: rgba(255, 255, 255, 0.25); }
.count.zero { opacity: 0.35; }

/* Linha de agendamento: faixa de cor à esquerda indica o status */
.appt { position: relative; overflow: hidden; padding: 16px 18px 16px 22px; }
.appt::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 5px; background: rgba(var(--v-theme-on-surface), 0.25); }
.s-pending::before { background: rgb(var(--v-theme-warning)); }
.s-confirmed::before { background: rgb(var(--v-theme-success)); }
.s-completed::before { background: rgb(var(--v-theme-primary)); }
.s-no_show::before { background: rgb(var(--v-theme-error)); }
.dim { opacity: 0.72; }
.appt-main { display: flex; gap: 20px; align-items: flex-start; }
.time { width: 64px; flex-shrink: 0; white-space: nowrap; }
.t1 { font-size: 1.35rem; font-weight: 650; letter-spacing: -0.02em; line-height: 1.1; }
.t2 { font-size: 0.75rem; opacity: 0.6; margin-top: 2px; }
.info { min-width: 0; flex: 1; }
.client { font-weight: 600; font-size: 1.02rem; }
.wa { color: inherit; text-decoration: none; display: inline-flex; align-items: center; gap: 5px; border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.35); }
.wa:hover { color: #1f8f4e; border-bottom-color: #1f8f4e; }
.wa-icon { color: #1f8f4e; }
.service { margin-top: 3px; font-size: 0.92rem; }
.phone { font-size: 0.8rem; opacity: 0.6; margin-top: 2px; }
.cancelled-by { margin-top: 6px; font-size: 0.8rem; color: rgb(var(--v-theme-error)); }
.notes { margin-top: 6px; font-size: 0.82rem; font-style: italic; opacity: 0.75; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08); }

.day-head { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; opacity: 0.6; margin: 18px 2px 8px; }
.next { max-width: 420px; margin-inline: auto; padding: 12px 14px; border-radius: 12px; background: rgba(var(--v-theme-primary), 0.07); }
.empty { text-align: center; padding: 56px 16px; opacity: 0.7; }
.fab { position: fixed; right: 18px; bottom: 18px; z-index: 5; }

@media (max-width: 600px) {
  .appt-main { gap: 14px; }
  .time { width: 58px; }
  .t1 { font-size: 1.15rem; }
  .t2 { font-size: 0.7rem; }
  .actions .v-btn { flex: 1 1 auto; }
  /* "Editar" vira só o ícone, para caber na mesma linha das outras ações */
  .actions .edit-btn { flex: 0 0 auto; min-width: 44px; padding: 0 10px; }
  .edit-label { display: none; }
  .actions .edit-btn :deep(.v-btn__prepend) { margin: 0; }
  .week { gap: 4px; }
  .week-day { padding: 8px 0 6px; border-radius: 10px; }
}
</style>
