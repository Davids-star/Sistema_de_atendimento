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
    days.value = byDay.map((d) => ({ date: d.date, total: d.total, done: d.by_status.completed ?? 0,
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
  <v-card class="breakdown pa-3">
    <div class="head">
      <div class="section-title d-flex align-center ga-1">
        Dia a dia
        <v-icon icon="mdi-information-outline" size="15" class="info" title="Faturamento = atendimentos concluídos." aria-label="Faturamento = atendimentos concluídos." />
      </div>
      <v-btn-toggle :model-value="mode" mandatory density="compact" color="primary" variant="outlined" divided
                    @update:model-value="setMode">
        <v-btn v-for="m in MODES" :key="m.value" :value="m.value" size="x-small">{{ m.title }}</v-btn>
      </v-btn-toggle>
    </div>

    <div class="nav">
      <v-btn icon="mdi-chevron-left" size="x-small" variant="text" title="Anterior" aria-label="Anterior" @click="move(-1)" />
      <span class="label num">{{ range.label }}</span>
      <v-btn icon="mdi-chevron-right" size="x-small" variant="text" title="Próximo" aria-label="Próximo" @click="move(1)" />
      <v-btn size="x-small" variant="tonal" class="ml-auto" :disabled="isToday" @click="goToday">Hoje</v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate height="2" class="mb-1" />
    <div v-if="error" class="text-body-small text-error">{{ error }}</div>

    <div v-else class="body">
      <div v-if="mode === 'day'" class="tiles">
        <div v-for="t in tiles" :key="t.label" class="tile">
          <div class="tile-value num">{{ t.value }}</div>
          <div class="tile-label">{{ t.label }}</div>
        </div>
      </div>

      <v-table v-else density="compact" class="compact">
        <thead>
          <tr><th>{{ mode === 'week' ? 'Dia' : 'Semana' }}</th><th class="r">Agend.</th><th class="r">Concl.</th><th class="r">Valor</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.key" :class="{ empty: !r.total && !r.cents }">
            <td>{{ r.label }}</td><td class="r num">{{ r.total }}</td><td class="r num">{{ r.done }}</td><td class="r num">{{ formatBRL(r.cents) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="totals"><td>Total</td><td class="r num">{{ totals.total }}</td><td class="r num">{{ totals.done }}</td><td class="r num">{{ formatBRL(totals.cents) }}</td></tr>
        </tfoot>
      </v-table>
    </div>
  </v-card>
</template>

<style scoped>
/* Tamanho fixo e pequeno: se um dia ficar maior que isso, rola por dentro e a página não cresce. */
.breakdown { max-height: 360px; display: flex; flex-direction: column; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.nav { display: flex; align-items: center; gap: 2px; margin-bottom: 6px; }
.label { font-size: 0.85rem; font-weight: 600; min-width: 130px; text-align: center; }
.body { overflow: auto; min-height: 0; }
.tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; padding: 6px 0; }
.tile { text-align: center; padding: 8px 4px; border-radius: 10px; background: rgba(var(--v-theme-on-surface), 0.045); }
.tile-value { font-size: 1.05rem; font-weight: 650; line-height: 1.2; }
.tile-label { font-size: 0.68rem; opacity: 0.65; margin-top: 2px; }
.compact { font-size: 0.82rem; }
.compact :deep(th), .compact :deep(td) { padding: 0 8px !important; height: 26px !important; white-space: nowrap; }
.compact :deep(th) { font-size: 0.66rem !important; }
.r { text-align: right; }
.empty td { opacity: 0.45; }
.totals td { font-weight: 700; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.2); }
.info { opacity: 0.5; cursor: help; }
@media (max-width: 600px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
