<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import DailyBreakdown from '../components/DailyBreakdown.vue'
import { formatBRL, formatPercent } from '../utils/format'
import { presetRange } from '../utils/period'

const PRESETS = [
  { value: 'this_month', title: 'mês' },
  { value: 'this_week', title: 'semana' },
  { value: 'today', title: 'hoje' },
]

const preset = ref('this_month')
const range = ref(presetRange('this_month'))
const loading = ref(false)
const error = ref('')
const summary = ref(null)
const revenue = ref(null)
let request = 0

const periodTitle = computed(() => PRESETS.find((p) => p.value === preset.value)?.title ?? '')

function onPreset(value) {
  preset.value = value
  range.value = presetRange(value)
  load()
}

async function load() {
  const mine = ++request
  loading.value = true
  error.value = ''
  summary.value = null
  revenue.value = null
  const params = { date_from: range.value.from, date_to: range.value.to }
  try {
    const [nextSummary, nextRevenue] = await Promise.all([
      api('/dashboard/summary', { params }),
      api('/dashboard/revenue', { params: { ...params, group_by: 'day' } }),
    ])
    if (mine !== request) return
    summary.value = nextSummary
    revenue.value = nextRevenue
  } catch (e) {
    if (mine === request) error.value = e.message
  } finally {
    if (mine === request) loading.value = false
  }
}
onMounted(load)

const topService = computed(() => summary.value?.top_services?.[0] ?? null)
const sparkBars = computed(() => {
  const pts = revenue.value?.points ?? []
  const last6 = pts.slice(-6)
  if (!last6.length) return []
  const max = Math.max(...last6.map((p) => p.revenue_cents || 0), 1)
  return last6.map((p) => Math.max(8, Math.round(((p.revenue_cents || 0) / max) * 100)))
})
</script>

<template>
  <div class="dashboard-container">
    <v-progress-linear v-if="loading" indeterminate color="primary" height="3" rounded class="mb-3" />

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" :text="error">
      <template #append><v-btn variant="text" size="small" @click="load">Tentar novamente</v-btn></template>
    </v-alert>

    <!-- Linha responsiva para desktop (duas colunas no desktop, uma coluna no celular) -->
    <div class="dash-grid">
      <!-- Coluna Principal / Esquerda no Desktop -->
      <div class="dash-col-left">
        <!-- 1. CARD HERO: FATURAMENTO REGISTRADO (Vinho com gradiente) -->
        <div class="card-hero mb-4">
          <div class="hero-left d-flex align-center ga-3">
            <div class="hero-icon-box">
              <v-icon icon="mdi-cash-multiple" size="26" />
            </div>
            <div>
              <div class="hero-label">Faturamento Registrado</div>
              <div class="hero-value">{{ summary ? formatBRL(summary.revenue_cents) : '—' }}</div>
              <div class="hero-sub d-flex align-center ga-1">
                <v-icon icon="mdi-calendar-range" size="14" />
                <span>{{ periodTitle }} selecionado</span>
              </div>
            </div>
          </div>
          <div v-if="sparkBars.length" class="hero-sparkline d-flex align-end ga-1" aria-hidden="true">
            <span v-for="(h, i) in sparkBars" :key="i" class="spark-bar" :style="{ height: h + '%' }"></span>
          </div>
          <span v-else-if="revenue" class="hero-empty">Sem faturamento concluído</span>
        </div>

        <!-- 2. CARD: SERVIÇOS MAIS REALIZADOS -->
        <div class="app-card service-card mb-4">
          <div class="card-header service-card-header d-flex align-center justify-space-between mb-3">
            <div class="service-card-heading d-flex align-center ga-2">
              <span class="wine-pill-indicator"></span>
              <span class="card-title">Serviços Mais Realizados</span>
            </div>
            <div class="period-toggle">
              <select :value="preset" class="period-dropdown" @change="onPreset($event.target.value)">
                <option v-for="p in PRESETS" :key="p.value" :value="p.value">{{ p.title }}</option>
              </select>
              <v-icon icon="mdi-chevron-down" size="16" class="select-chevron" />
            </div>
          </div>

          <div class="service-content">
            <div class="service-main">
              <div class="service-icon-circle">
                <v-icon icon="mdi-content-cut" color="#6b1322" size="24" />
              </div>
              <div v-if="topService" class="service-details">
                <div class="text-caption text-medium-emphasis text-truncate">
                  {{ topService.name }} · {{ periodTitle }}
                </div>
                <div class="stat-highlight text-wine">
                  {{ topService.count }} vezes
                </div>
              </div>
              <div v-else class="empty-state">{{ summary ? 'Nenhum serviço concluído neste período.' : '—' }}</div>
            </div>

            <div v-if="topService" class="service-total">
              <div class="text-caption text-medium-emphasis">Total faturado nesse serviço</div>
              <div class="stat-highlight text-green">
                {{ formatBRL(topService.revenue_cents) }}
              </div>
            </div>
          </div>
        </div>

        <!-- 3. DUPLA DE CARDS DE MÉTRICAS LADO A LADO -->
        <div class="metric-row ga-3 mb-4">
          <!-- Card Agendamentos -->
          <router-link :to="{ name: 'appointments' }" class="app-card flex-1-1 metric-card text-decoration-none">
            <div class="d-flex align-center justify-space-between">
              <div class="d-flex align-center ga-3">
                <div class="metric-icon-circle icon-green">
                  <v-icon icon="mdi-calendar-check-outline" color="#3c763d" size="22" />
                </div>
                <div>
                  <div class="metric-title">Agendamentos</div>
                  <div class="metric-num">{{ summary?.scheduled_appointments ?? '—' }}</div>
                  <div class="metric-sub">Concluídos: {{ summary?.by_status?.completed ?? '—' }}</div>
                </div>
              </div>
              <div class="metric-arrow">
                <v-icon icon="mdi-chevron-right" size="18" color="#7e6367" />
              </div>
            </div>
          </router-link>

          <!-- Card Faturamento Previsto -->
          <router-link :to="{ name: 'appointments' }" class="app-card flex-1-1 metric-card text-decoration-none">
            <div class="d-flex align-center justify-space-between">
              <div class="d-flex align-center ga-3">
                <div class="metric-icon-circle icon-wine">
                  <v-icon icon="mdi-sack" color="primary" size="22" />
                </div>
                <div>
                  <div class="metric-title">Faturamento Previsto</div>
                  <div class="metric-num">{{ summary ? formatBRL(summary.expected_revenue_cents) : '—' }}</div>
                  <div class="metric-sub">Pendentes e Confirmados</div>
                </div>
              </div>
              <div class="metric-arrow">
                <v-icon icon="mdi-chevron-right" size="18" color="#7e6367" />
              </div>
            </div>
          </router-link>

          <div class="app-card flex-1-1 metric-card">
            <div class="d-flex align-center ga-3">
              <div class="metric-icon-circle icon-wine">
                <v-icon icon="mdi-account-clock-outline" color="primary" size="22" />
              </div>
              <div>
                <div class="metric-title">Taxa de ausência</div>
                <div class="metric-num">{{ summary ? formatPercent(summary.no_show_rate) : '—' }}</div>
                <div class="metric-sub">No período selecionado</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Coluna com o detalhamento diário -->
      <div class="dash-col-right">
        <DailyBreakdown />
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-container {
  width: 100%;
}

/* Grid responsivo: 1 coluna no celular/tablet, 2 colunas amplas no desktop */
.dash-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

@media (min-width: 960px) {
  .dash-grid {
    display: grid;
    grid-template-columns: 1.15fr 1fr;
    gap: 20px;
    align-items: start;
  }
}

.min-w-0 {
  min-width: 0;
}

.service-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
}

.service-card-heading {
  min-width: 0;
}

.service-content {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  align-items: center;
  min-height: 82px;
}

.service-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding-right: 16px;
}

.service-main:only-child {
  grid-column: 1 / -1;
  padding-right: 0;
}

.service-details {
  min-width: 0;
  flex: 1;
  text-align: center;
}

.service-total {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  padding-left: 16px;
  border-left: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  text-align: center;
}

/* 1. Card de faturamento */
.card-hero {
  background: rgb(var(--v-theme-primary));
  border-radius: 22px;
  padding: 20px 22px;
  color: rgb(var(--v-theme-on-primary));
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 8px 24px rgba(107, 19, 34, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.hero-icon-box {
  width: 50px;
  height: 50px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.12);
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.18);
  flex-shrink: 0;
}

.hero-label {
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-primary), 0.82);
  font-weight: 500;
}

.hero-value {
  font-size: 1.85rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 2px 0;
}

.hero-sub {
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-primary), 0.7);
}
.hero-empty { font-size: 0.72rem; color: rgba(var(--v-theme-on-primary), 0.75); }

.hero-sparkline {
  height: 48px;
  width: 70px;
  flex-shrink: 0;
}

.spark-bar {
  flex: 1;
  background: rgba(var(--v-theme-on-primary), 0.22);
  border-radius: 3px 3px 0 0;
  min-height: 6px;
}

/* 2. Cartões */
.app-card {
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  border-radius: 20px;
  padding: 16px 18px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
}

.wine-pill-indicator {
  display: inline-block;
  width: 5px;
  height: 18px;
  background: rgb(var(--v-theme-primary));
  border-radius: 4px;
}

.card-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: rgb(var(--v-theme-primary));
  letter-spacing: -0.01em;
}

.period-toggle {
  position: relative;
  display: flex;
  align-items: center;
}

.period-dropdown {
  appearance: none;
  background: rgb(var(--v-theme-surface-variant));
  border: 1px solid rgba(var(--v-theme-on-surface), 0.15);
  border-radius: 12px;
  padding: 3px 24px 3px 10px;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
  cursor: pointer;
  outline: none;
}

.select-chevron {
  position: absolute;
  right: 6px;
  pointer-events: none;
  color: rgb(var(--v-theme-primary));
}

.service-icon-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.1);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.stat-highlight {
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  margin-top: 2px;
}

.text-wine {
  color: rgb(var(--v-theme-primary));
}

.text-green {
  color: rgb(var(--v-theme-success));
}

/* 3. Métricas duplas */
.metric-row {
  display: flex;
  flex-wrap: wrap;
}

.metric-card {
  min-width: 220px;
  transition: transform 0.15s, box-shadow 0.15s;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}

.metric-icon-circle {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.icon-green {
  background: rgba(var(--v-theme-success), 0.12);
}

.icon-wine {
  background: rgba(var(--v-theme-primary), 0.1);
}

.metric-title {
  font-size: 0.74rem;
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-weight: 600;
}

.metric-num {
  font-size: 1.25rem;
  font-weight: 800;
  color: rgb(var(--v-theme-on-surface));
  line-height: 1.15;
  margin: 1px 0;
}

.metric-sub {
  font-size: 0.68rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.metric-arrow {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.08);
  display: grid;
  place-items: center;
}
.empty-state { color: rgba(var(--v-theme-on-surface), 0.68); font-size: 0.85rem; }

@media (max-width: 480px) {
  .metric-card {
    min-width: 100%;
  }

  .service-content {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
  }

  .service-main {
    padding-right: 0;
  }

  .service-total {
    align-self: auto;
    padding: 12px 0 0;
    border-left: 0;
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  }
}
</style>
