<script setup>
// "Dia a dia": quadro PEQUENO e de altura limitada. O dono escolhe ver um dia, uma semana ou um mês, e navega para trás/frente.
// Nunca cresce com a quantidade de dados: dia = 4 números; semana = 7 linhas; mês = até 6 linhas (resumo por semana).
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { addDays, todayISO, weekdayShort } from '../utils/datetime'
import { formatBRL, formatDayMonth } from '../utils/format'
import { shiftAnchor, viewRange, weekBuckets } from '../utils/period'

const MODES = [{ value: 'day', title: 'Dia' }, { value: 'week', title: 'Semana' }, { value: 'month', title: 'Mês' }]

const mode = ref('week')
const anchor = ref(todayISO())
const days = ref([])        // [{ date, total, done, noShow, cents }]
const loading = ref(false)
const error = ref('')
let request = 0             // ignora respostas antigas se a pessoa clicar rápido

const range = computed(() => viewRange(mode.value, anchor.value))
const isToday = computed(() => range.value.from <= todayISO() && todayISO() <= range.value.to)

async function load() {
  const mine = ++request
  loading.value = true
  error.value = ''
  const { from, to } = range.value
  try {
    const [byDay, revenue] = await Promise.all([
      api('/dashboard/appointments-by-day', { params: { date_from: from, date_to: to } }),
      api('/dashboard/revenue', { params: { date_from: from, date_to: to, group_by: 'day' } }),
    ])
    if (mine !== request) return
    const cents = new Map(revenue.points.map((p) => [p.period, p.revenue_cents]))
    // "Agendamentos" não conta os cancelados (o horário voltou a ficar livre), igual ao cartão do dashboard.
    days.value = byDay.map((d) => ({ date: d.date, total: d.total - (d.by_status.cancelled ?? 0), done: d.by_status.completed ?? 0,
      noShow: d.by_status.no_show ?? 0, cents: cents.get(d.date) ?? 0 }))
  } catch (e) {
    if (mine === request) error.value = e.message
  } finally {
    if (mine === request) loading.value = false
  }
}
onMounted(load)
watch([mode, anchor], load)

const sum = (list) => list.reduce((t, d) => ({ total: t.total + d.total, done: t.done + d.done, noShow: t.noShow + d.noShow, cents: t.cents + d.cents }),
  { total: 0, done: 0, noShow: 0, cents: 0 })

const rows = computed(() => {
  if (mode.value === 'week') return days.value.map((d) => ({ key: d.date, label: `${weekdayShort(d.date)} ${formatDayMonth(d.date)}`, ...d }))
  if (mode.value === 'month') {
    return weekBuckets(range.value.from, range.value.to).map((b) => ({
      key: b.from, label: b.label, ...sum(days.value.filter((d) => d.date >= b.from && d.date <= b.to)) }))
  }
  return []
})
const totals = computed(() => sum(days.value))
const peakDay = computed(() => days.value.reduce((best, day) => day.total > (best?.total ?? 0) ? day : best, null))
const tiles = computed(() => [
  { label: 'Agendamentos', value: totals.value.total },
  { label: 'Concluídos', value: totals.value.done },
  { label: 'Ausências', value: totals.value.noShow },
  { label: 'Faturamento', value: formatBRL(totals.value.cents) },
])

const move = (dir) => { anchor.value = shiftAnchor(mode.value, anchor.value, dir) }
const goToday = () => { anchor.value = todayISO() }
const setMode = (value) => { mode.value = value }
</script>

<template>
  <v-card class="breakdown pa-0" elevation="0">
    <div class="head">
      <div class="section-title d-flex align-center">
        <v-icon icon="mdi-calendar-check-outline" size="22" class="mr-2 text-white" />
        <span class="text-white font-weight-bold" style="font-size: 1rem;">Agendamentos por dia</span>
        <v-icon icon="mdi-information-outline" size="16" class="info ml-1" title="Faturamento = atendimentos concluídos." aria-label="Faturamento = atendimentos concluídos." />
      </div>
      <v-btn-toggle :model-value="mode" mandatory density="compact" variant="flat" class="mode-toggle"
                    @update:model-value="setMode">
        <v-btn v-for="m in MODES" :key="m.value" :value="m.value" size="x-small" class="mode-btn" :class="{ 'mode-btn-active': mode === m.value }">{{ m.title }}</v-btn>
      </v-btn-toggle>
    </div>

    <div class="nav px-3 py-1">
      <v-btn icon="mdi-chevron-left" size="x-small" variant="text" color="primary" title="Anterior" aria-label="Anterior" @click="move(-1)" />
      <span class="label num">{{ range.label }}</span>
      <v-btn icon="mdi-chevron-right" size="x-small" variant="text" color="primary" title="Próximo" aria-label="Próximo" @click="move(1)" />
      <v-btn size="x-small" variant="tonal" color="primary" class="ml-auto" :disabled="isToday" @click="goToday">Hoje</v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate height="2" color="primary" />
    <div v-if="error" class="text-body-small text-error pa-3">{{ error }}</div>

    <div v-else class="body px-2 pb-2">
      <div v-if="mode !== 'day' && peakDay?.total" class="peak-day mx-2 mt-2">
        <v-icon icon="mdi-trending-up" size="18" />
        <span>
          Dia com mais agendamentos:
          <strong>{{ weekdayShort(peakDay.date) }} {{ formatDayMonth(peakDay.date) }}</strong>
          · {{ peakDay.total }}
        </span>
      </div>

      <div v-if="mode === 'day'" class="tiles pa-2">
        <div v-for="t in tiles" :key="t.label" class="tile">
          <div class="tile-value num">{{ t.value }}</div>
          <div class="tile-label">{{ t.label }}</div>
        </div>
      </div>

      <v-table v-else density="compact" class="compact">
        <thead>
          <tr>
            <th>{{ mode === 'week' ? 'DIA' : 'SEMANA' }}</th>
            <th class="r">AGEND.</th>
            <th class="r">CONCL.</th>
            <th class="r">VALOR</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.key" :class="{ empty: !r.total && !r.cents }">
            <td class="font-weight-medium">{{ r.label }}</td>
            <td class="r num">{{ r.total }}</td>
            <td class="r num">{{ r.done }}</td>
            <td class="r num">{{ formatBRL(r.cents) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="totals">
            <td>Total</td>
            <td class="r num">{{ totals.total }}</td>
            <td class="r num">{{ totals.done }}</td>
            <td class="r num">{{ formatBRL(totals.cents) }}</td>
          </tr>
        </tfoot>
      </v-table>
    </div>
  </v-card>
</template>

<style scoped>
/* Tamanho fixo e pequeno: se um dia ficar maior que isso, rola por dentro e a página não cresce. */
.breakdown {
  max-height: 360px;
  display: flex;
  flex-direction: column;
  border-radius: 20px !important;
  background: rgb(var(--v-theme-surface)) !important;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 16px;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}
.mode-toggle {
  background: rgba(255, 255, 255, 0.16) !important;
  border-radius: 20px !important;
  padding: 3px !important;
  height: 28px !important;
  border: none !important;
}
.mode-btn {
  border-radius: 16px !important;
  min-height: 22px !important;
  height: 22px !important;
  padding: 0 10px !important;
  font-size: 0.72rem !important;
  font-weight: 500 !important;
  color: rgba(255, 255, 255, 0.8) !important;
  background: transparent !important;
  box-shadow: none !important;
}
.mode-btn-active {
  background: rgb(var(--v-theme-secondary)) !important;
  color: rgb(var(--v-theme-on-secondary)) !important;
  font-weight: 700 !important;
}
.nav {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgb(var(--v-theme-surface-variant));
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.label {
  font-size: 0.82rem;
  font-weight: 600;
  min-width: 130px;
  text-align: center;
  color: rgb(var(--v-theme-primary));
}
.peak-day {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border-radius: 10px;
  background: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.78rem;
}
.peak-day :deep(.v-icon) { color: rgb(var(--v-theme-primary)); }
.body {
  overflow: auto;
  min-height: 0;
  background: #FFFFFF;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.tile {
  text-align: center;
  padding: 10px 4px;
  border-radius: 12px;
  background: rgb(var(--v-theme-surface-variant));
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}
.tile-value {
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1.2;
  color: rgb(var(--v-theme-primary));
}
.tile-label {
  font-size: 0.68rem;
  color: rgba(var(--v-theme-on-surface), 0.72);
  margin-top: 2px;
  font-weight: 500;
}
.compact {
  font-size: 0.82rem;
  background: rgb(var(--v-theme-surface)) !important;
}
.compact :deep(th), .compact :deep(td) {
  padding: 0 10px !important;
  height: 28px !important;
  white-space: nowrap;
}
.compact :deep(th) {
  font-size: 0.68rem !important;
  font-weight: 800 !important;
  color: rgb(var(--v-theme-primary)) !important;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1) !important;
}
.compact :deep(td) {
  color: rgb(var(--v-theme-on-surface));
  border-bottom: 1px solid rgba(0, 0, 0, 0.04) !important;
}
.r { text-align: right; }
.empty td { opacity: 0.45; }
.totals td {
  font-weight: 800 !important;
  color: rgb(var(--v-theme-on-surface));
  border-top: 1.5px solid rgba(var(--v-theme-on-surface), 0.2) !important;
}
.info {
  opacity: 0.7;
  cursor: help;
  color: #FFFFFF;
}
@media (max-width: 600px) {
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
