<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import BarChart from '../components/BarChart.vue'
import DailyBreakdown from '../components/DailyBreakdown.vue'
import { formatBRL, formatDayMonth, formatPercent } from '../utils/format'
import { daysBetween, presetRange } from '../utils/period'

const PRESETS = [
  { value: 'today', title: 'Hoje' },
  { value: 'this_week', title: 'Esta semana' },
  { value: 'this_month', title: 'Este mês' },
  { value: 'last_month', title: 'Mês passado' },
  { value: 'last_30', title: 'Últimos 30 dias' },
  { value: 'custom', title: 'Personalizado' },
]
const MAX_DAYS = 366
const STATUS_LABEL = { pending: 'Pendentes', confirmed: 'Confirmados', completed: 'Concluídos', no_show: 'Ausências', cancelled: 'Cancelados' }
const STATUS_COLOR = { pending: 'warning', confirmed: 'success', completed: 'primary', no_show: 'error', cancelled: 'neutral' }
const statusShare = (n) => (summary.value?.total_appointments ? `${(n / summary.value.total_appointments) * 100}%` : '0%')

const preset = ref('this_month')
const range = ref(presetRange('this_month'))
const loading = ref(false)
const error = ref('')
const summary = ref(null)
const byDay = ref([])
const revenue = ref(null)
const pendingOutcome = ref(0)
const PENDING_LIMIT = 200

const rangeError = computed(() => {
  const { from, to } = range.value
  if (!from || !to) return 'Informe as duas datas.'
  if (to < from) return 'A data final deve ser igual ou posterior à inicial.'
  if (daysBetween(from, to) > MAX_DAYS) return `Período máximo de ${MAX_DAYS} dias.`
  return ''
})

function onPreset(value) {
  preset.value = value
  if (value !== 'custom') { range.value = presetRange(value); load() }
}

async function load() {
  if (rangeError.value) return
  loading.value = true
  error.value = ''
  const params = { date_from: range.value.from, date_to: range.value.to }
  const group_by = daysBetween(range.value.from, range.value.to) > 92 ? 'month' : 'day'
  try {
    ;[summary.value, byDay.value, revenue.value] = await Promise.all([
      api('/dashboard/summary', { params }),
      api('/dashboard/appointments-by-day', { params }),
      api('/dashboard/revenue', { params: { ...params, group_by } }),
    ])
    const stale = await api('/appointments', { params: { needs_outcome: true, limit: PENDING_LIMIT } })
    pendingOutcome.value = stale.length
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)

const cards = computed(() => {
  const s = summary.value
  if (!s) return []
  return [
    { title: 'Agendamentos', value: s.total_appointments, icon: 'mdi-calendar-check', sub: `${s.by_status.completed} concluídos` },
    { title: 'Faturamento registrado', value: formatBRL(s.revenue_cents), icon: 'mdi-cash-check', sub: 'Somente atendimentos concluídos' },
    { title: 'Faturamento previsto', value: formatBRL(s.expected_revenue_cents), icon: 'mdi-cash-clock', sub: 'Pendentes e confirmados' },
    { title: 'Taxa de ausência', value: formatPercent(s.no_show_rate), icon: 'mdi-account-cancel-outline',
      sub: s.no_show_rate === null ? 'Sem atendimentos finalizados' : `${s.by_status.no_show} ausência(s)` },
    { title: 'Clientes atendidos', value: s.unique_clients, icon: 'mdi-account-multiple-outline', sub: 'Clientes diferentes no período' },
    { title: 'Clientes novos', value: s.new_clients, icon: 'mdi-account-plus-outline', sub: 'Cadastrados no período' },
  ]
})

const dayItems = computed(() => byDay.value.map((d) => ({
  label: formatDayMonth(d.date), value: d.total, tip: `${formatDayMonth(d.date)}: ${d.total} agendamento(s)`,
})))

// A receita por dia só traz dias com faturamento; completa com zeros para o gráfico ficar contínuo.
const revenueItems = computed(() => {
  if (!revenue.value) return []
  const byPeriod = new Map(revenue.value.points.map((p) => [p.period, p.revenue_cents]))
  if (revenue.value.group_by === 'month') {
    return revenue.value.points.map((p) => ({
      label: `${p.period.slice(5)}/${p.period.slice(2, 4)}`, value: p.revenue_cents, tip: `${p.period}: ${formatBRL(p.revenue_cents)}`,
    }))
  }
  return byDay.value.map((d) => {
    const v = byPeriod.get(d.date) ?? 0
    return { label: formatDayMonth(d.date), value: v, tip: `${formatDayMonth(d.date)}: ${formatBRL(v)}` }
  })
})
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-6">
    <div class="mr-auto">
      <div class="eyebrow mb-1">Visão geral</div>
      <h1 class="page-title">Dashboard</h1>
    </div>
    <v-btn-toggle class="d-none d-sm-flex" :model-value="preset" mandatory density="comfortable" color="primary"
                  variant="outlined" divided @update:model-value="onPreset">
      <v-btn v-for="p in PRESETS" :key="p.value" :value="p.value" size="small">{{ p.title }}</v-btn>
    </v-btn-toggle>
    <!-- No celular os 4 botões não cabem: vira uma lista de seleção -->
    <v-select class="d-sm-none period-select" :model-value="preset" :items="PRESETS" item-title="title" item-value="value"
              density="compact" hide-details aria-label="Período" @update:model-value="onPreset" />
  </div>

  <v-row v-if="preset === 'custom'" class="mb-1">
    <v-col cols="12" sm="4" md="3">
      <v-text-field v-model="range.from" label="De" type="date" hide-details="auto" />
    </v-col>
    <v-col cols="12" sm="4" md="3">
      <v-text-field v-model="range.to" label="Até" type="date" hide-details="auto" :error-messages="rangeError" />
    </v-col>
    <v-col cols="12" sm="4" md="3" class="d-flex align-start">
      <v-btn color="primary" size="large" :disabled="!!rangeError" :loading="loading" @click="load">Aplicar</v-btn>
    </v-col>
  </v-row>

  <v-alert v-if="error" type="error" variant="tonal" class="mb-4" :text="error">
    <template #append><v-btn variant="text" @click="load">Tentar de novo</v-btn></template>
  </v-alert>

  <v-alert v-if="pendingOutcome > 0" type="warning" variant="tonal" class="mb-4" icon="mdi-clock-alert-outline">
    <strong>{{ pendingOutcome >= PENDING_LIMIT ? `${PENDING_LIMIT}+` : pendingOutcome }}
      agendamento(s)</strong> já terminaram e ainda não foram marcados como concluídos ou ausentes.
    O faturamento e a taxa de ausência só contam atendimentos finalizados.
    <template #append>
      <v-btn variant="text" size="small" :to="{ name: 'appointments' }">Revisar</v-btn>
    </template>
  </v-alert>

  <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" rounded />

  <template v-if="summary">
    <div class="grid grid-kpi">
      <v-card v-for="(c, i) in cards" :key="c.title" class="kpi" :class="{ feature: i === 1 }">
        <div class="kpi-head">
          <span class="kpi-icon"><v-icon :icon="c.icon" size="20" /></span>
          <span class="eyebrow">{{ c.title }}</span>
        </div>
        <div class="kpi-value num">{{ c.value }}</div>
        <div class="kpi-sub">{{ c.sub }}</div>
      </v-card>
    </div>

    <div class="grid grid-2 mt-4">
      <v-card class="pa-5">
        <div class="section-title mb-4">Agendamentos por dia</div>
        <BarChart :items="dayItems" />
      </v-card>
      <v-card class="pa-5">
        <div class="d-flex align-baseline mb-4">
          <div class="section-title mr-auto">Faturamento registrado</div>
          <div class="text-body-small text-medium-emphasis">Total <strong class="num">{{ formatBRL(revenue?.total_cents) }}</strong></div>
        </div>
        <BarChart :items="revenueItems" color="secondary" :format="formatBRL" />
      </v-card>
    </div>

    <div class="grid grid-2 mt-4">
      <DailyBreakdown />
      <v-card class="pa-5">
        <div class="section-title mb-4">Situação dos agendamentos</div>
        <div v-for="(label, key) in STATUS_LABEL" :key="key" class="status-row">
          <span class="dot" :style="{ background: `rgb(var(--v-theme-${STATUS_COLOR[key]}))` }" />
          <span class="status-label">{{ label }}</span>
          <span class="bar-track"><span class="bar-fill" :style="{ width: statusShare(summary.by_status[key]), background: `rgb(var(--v-theme-${STATUS_COLOR[key]}))` }" /></span>
          <span class="num status-count">{{ summary.by_status[key] }}</span>
        </div>
      </v-card>
    </div>

    <v-card class="pa-5 mt-4">
      <div class="section-title mb-4">Serviços mais realizados</div>
      <v-table v-if="summary.top_services.length" density="comfortable">
        <thead><tr><th>Serviço</th><th class="text-right">Qtd.</th><th class="text-right">Faturamento</th></tr></thead>
        <tbody>
          <tr v-for="s in summary.top_services" :key="s.service_id">
            <td class="font-weight-medium">{{ s.name }}</td><td class="text-right num">{{ s.count }}</td>
            <td class="text-right num">{{ formatBRL(s.revenue_cents) }}</td>
          </tr>
        </tbody>
      </v-table>
      <div v-else class="text-body-medium text-medium-emphasis">Nenhum atendimento concluído no período.</div>
    </v-card>
  </template>
</template>

<style scoped>
/* seletor de período no celular ocupa a largura toda */
.period-select { flex: 1 1 100%; }
.kpi { padding: 20px 22px; display: flex; flex-direction: column; gap: 6px; }
.kpi-head { display: flex; align-items: center; gap: 10px; }
.kpi-icon { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
            background: rgba(var(--v-theme-primary), 0.09); color: rgb(var(--v-theme-primary)); }
.kpi-value { font-size: 2rem; font-weight: 650; letter-spacing: -0.02em; line-height: 1.15; margin-top: 6px; }
.kpi-sub { font-size: 0.8rem; color: rgba(var(--v-theme-on-surface), 0.6); }

/* Cartão de destaque (faturamento registrado) */
.kpi.feature { background: var(--ink); border-color: transparent !important; color: #f3ece0; }
.kpi.feature .kpi-icon { background: rgba(159, 195, 184, 0.18); color: #bfe0d5; }
.kpi.feature .kpi-sub { color: rgba(243, 236, 224, 0.62); }
.v-theme--dark .kpi.feature { background: linear-gradient(145deg, #1f2b27, #171d27); border: 1px solid rgba(159, 195, 184, 0.3) !important; }

.status-row { display: grid; grid-template-columns: 10px 110px 1fr 40px; align-items: center; gap: 12px; padding: 7px 0; }
.dot { width: 10px; height: 10px; border-radius: 50%; }
.status-label { font-size: 0.9rem; }
.bar-track { height: 8px; border-radius: 4px; background: rgba(var(--v-theme-on-surface), 0.07); overflow: hidden; }
.bar-fill { display: block; height: 100%; border-radius: 4px; min-width: 2px; opacity: 0.85; }
.status-count { text-align: right; font-weight: 600; }
</style>
