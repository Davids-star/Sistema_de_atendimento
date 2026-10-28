<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import BarChart from '../components/BarChart.vue'
import { formatBRL, formatDayMonth, formatPercent } from '../utils/format'
import { daysBetween, presetRange } from '../utils/period'

const PRESETS = [
  { value: 'this_month', title: 'Este mês' },
  { value: 'last_month', title: 'Mês passado' },
  { value: 'last_30', title: 'Últimos 30 dias' },
  { value: 'custom', title: 'Personalizado' },
]
const MAX_DAYS = 366
const STATUS_LABEL = { pending: 'Pendentes', confirmed: 'Confirmados', completed: 'Concluídos', no_show: 'Ausências', cancelled: 'Cancelados' }

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
  <div class="d-flex flex-wrap align-center ga-3 mb-4">
    <h1 class="text-headline-small mr-auto">Dashboard</h1>
    <v-btn-toggle :model-value="preset" mandatory density="comfortable" color="primary" variant="outlined"
                  divided @update:model-value="onPreset">
      <v-btn v-for="p in PRESETS" :key="p.value" :value="p.value" size="small">{{ p.title }}</v-btn>
    </v-btn-toggle>
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
    {{ pendingOutcome >= PENDING_LIMIT ? `${PENDING_LIMIT}+` : pendingOutcome }}
    agendamento(s) já terminaram e ainda não foram marcados como concluídos ou ausentes.
    Os indicadores de faturamento e ausência só contam atendimentos finalizados.
  </v-alert>

  <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

  <template v-if="summary">
    <v-row>
      <v-col v-for="c in cards" :key="c.title" cols="12" sm="6" lg="4" xl="2">
        <v-card class="pa-4 h-100">
          <div class="d-flex align-center text-body-medium text-medium-emphasis">
            <v-icon :icon="c.icon" size="20" class="mr-2" />{{ c.title }}
          </div>
          <div class="text-headline-medium font-weight-medium my-1">{{ c.value }}</div>
          <div class="text-body-small text-medium-emphasis">{{ c.sub }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" lg="6">
        <v-card class="pa-4 h-100">
          <div class="text-title-medium mb-3">Agendamentos por dia</div>
          <BarChart :items="dayItems" />
        </v-card>
      </v-col>
      <v-col cols="12" lg="6">
        <v-card class="pa-4 h-100">
          <div class="d-flex align-baseline mb-3">
            <div class="text-title-medium mr-auto">Faturamento registrado</div>
            <div class="text-body-medium text-medium-emphasis">Total: {{ formatBRL(revenue?.total_cents) }}</div>
          </div>
          <BarChart :items="revenueItems" color="secondary" />
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" md="6">
        <v-card class="pa-4 h-100">
          <div class="text-title-medium mb-3">Situação dos agendamentos</div>
          <v-list density="compact" class="pa-0">
            <v-list-item v-for="(label, key) in STATUS_LABEL" :key="key" :title="label" class="px-0">
              <template #append><span class="font-weight-medium">{{ summary.by_status[key] }}</span></template>
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card class="pa-4 h-100">
          <div class="text-title-medium mb-3">Serviços mais realizados</div>
          <v-table v-if="summary.top_services.length" density="comfortable">
            <thead><tr><th>Serviço</th><th class="text-right">Qtd.</th><th class="text-right">Faturamento</th></tr></thead>
            <tbody>
              <tr v-for="s in summary.top_services" :key="s.service_id">
                <td>{{ s.name }}</td><td class="text-right">{{ s.count }}</td>
                <td class="text-right">{{ formatBRL(s.revenue_cents) }}</td>
              </tr>
            </tbody>
          </v-table>
          <div v-else class="text-body-medium text-medium-emphasis">Nenhum atendimento concluído no período.</div>
        </v-card>
      </v-col>
    </v-row>
  </template>
</template>
