<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, setToken } from '../api'
import { formatPhone } from '../utils/format'
import { flattenDays, groupByWeekday, validateIntervals, WEEKDAYS } from '../utils/hours'
import { formatDateTime, isoToLocalInput, localInputToISO } from '../utils/datetime'
import { notify, notifyError } from '../utils/notify'
import { passwordError } from '../utils/password'
import { phoneError } from '../utils/phone'

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

// ---------- minha conta: alterar senha ----------
const hasPassword = ref(true)   // admin que só entra com Google ainda não tem senha: não precisa informar a atual
const pw = ref({ current: '', next: '', confirm: '' })
const showPw = ref(false)
const pwSaving = ref(false)
const pwProblem = computed(() => passwordError(pw.value.next, pw.value.confirm))
const pwOk = computed(() => !pwProblem.value && (!hasPassword.value || !!pw.value.current))

async function changePassword() {
  pwSaving.value = true
  try {
    const r = await api('/auth/change-password', { method: 'POST', body: {
      current_password: hasPassword.value ? pw.value.current : null, new_password: pw.value.next } })
    setToken(r.access_token)   // a troca encerra as sessões antigas; este token novo mantém você logado
    hasPassword.value = true
    pw.value = { current: '', next: '', confirm: '' }
    notify('Senha alterada. Outros dispositivos conectados foram desconectados.')
  } catch (e) { notifyError(e) }
  finally { pwSaving.value = false }
}

// ---------- WhatsApp do dono (para onde o bot encaminha quem precisa falar com uma pessoa) ----------
const contactPhone = ref('')
const contactSaving = ref(false)
const contactProblem = computed(() => (contactPhone.value.trim() ? phoneError(contactPhone.value) : ''))

async function saveContact() {
  contactSaving.value = true
  try {
    const r = await api('/settings', { method: 'PUT', body: { contact_phone: contactPhone.value.trim() || null } })
    contactPhone.value = r.contact_phone ? formatPhone(r.contact_phone) : ''
    notify(r.contact_phone ? 'WhatsApp de atendimento salvo' : 'WhatsApp de atendimento removido')
  } catch (e) { notifyError(e) }
  finally { contactSaving.value = false }
}

onMounted(async () => {
  api('/auth/me').then((me) => { hasPassword.value = me?.has_password !== false }).catch(() => {})
  try {
    const [s, hours] = await Promise.all([api('/settings'), api('/business-hours')])
    interval.value = s.slot_interval_minutes
    contactPhone.value = s.contact_phone ? formatPhone(s.contact_phone) : ''
    days.value = groupByWeekday(hours)
  } catch (e) { notifyError(e) }
  loadBlocks()
})
</script>

<template>
  <div class="mb-6"><div class="eyebrow mb-1">Funcionamento</div><h1 class="page-title">Configurações</h1></div>

  <v-card class="pa-5 mb-4">
    <div class="section-title">Intervalo entre horários</div>
    <p class="text-body-medium text-medium-emphasis mb-3">
      De quanto em quanto tempo começam os horários oferecidos ao cliente (ex.: 30 min → 9:00, 9:30, 10:00…).
    </p>
    <div class="d-flex flex-wrap align-center ga-3">
      <v-chip-group :model-value="+interval" mandatory selected-class="text-primary" @update:model-value="(v) => v && (interval = v)">
        <v-chip v-for="m in INTERVAL_PRESETS" :key="m" :value="m" filter variant="outlined">{{ m }} min</v-chip>
      </v-chip-group>
      <v-text-field v-model="interval" label="Outro valor (min)" type="number" hide-details density="compact"
                    style="max-width: 170px" :error="!intervalOk" />
      <v-btn color="primary" :loading="intervalSaving" :disabled="!intervalOk" @click="saveInterval">Salvar</v-btn>
    </div>
  </v-card>

  <v-card class="pa-5 mb-5">
    <div class="section-title">WhatsApp de atendimento</div>
    <p class="text-body-medium text-medium-emphasis mb-3">
      Quando a cliente pedir para falar com uma pessoa, o bot manda este número, num botão que abre o WhatsApp.
      Deixe em branco para o bot só avisar que você vai responder.
    </p>
    <div class="d-flex flex-wrap align-start ga-3">
      <v-text-field v-model="contactPhone" label="WhatsApp (com DDD)" inputmode="tel" hide-details="auto" style="max-width: 260px"
                    prepend-inner-icon="mdi-whatsapp" :error-messages="contactProblem" />
      <v-btn color="primary" size="large" :loading="contactSaving" :disabled="!!contactProblem" @click="saveContact">Salvar</v-btn>
    </div>
  </v-card>

  <v-card class="pa-5 mb-4">
    <div class="section-title">Horário de funcionamento</div>
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

  <v-card class="pa-5">
    <div class="section-title">Bloqueios</div>
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

  <v-card class="pa-5 mt-5">
    <div class="section-title">Minha conta · Alterar senha</div>
    <p class="text-body-medium text-medium-emphasis mb-3">
      <template v-if="hasPassword">Informe a senha atual e escolha uma nova (mínimo de 10 caracteres). Os outros dispositivos conectados serão desconectados.</template>
      <template v-else>Você entra com o Google e ainda não tem senha. Crie uma se quiser também poder entrar com e-mail e senha.</template>
    </p>
    <v-form class="pw-form" @submit.prevent="changePassword">
      <v-text-field v-if="hasPassword" v-model="pw.current" label="Senha atual" :type="showPw ? 'text' : 'password'" autocomplete="current-password" />
      <v-text-field v-model="pw.next" label="Nova senha" :type="showPw ? 'text' : 'password'" autocomplete="new-password"
                    :append-inner-icon="showPw ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" @click:append-inner="showPw = !showPw" />
      <v-text-field v-model="pw.confirm" label="Repita a nova senha" :type="showPw ? 'text' : 'password'" autocomplete="new-password"
                    :error-messages="pw.confirm && pwProblem ? pwProblem : ''" />
      <v-btn type="submit" color="primary" :loading="pwSaving" :disabled="!pwOk">{{ hasPassword ? 'Alterar senha' : 'Criar senha' }}</v-btn>
    </v-form>
  </v-card>
</template>

<style scoped>
.pw-form { max-width: 420px; }
.v-list-item :deep(.v-list-item-title) { white-space: normal; }
.day-row { display: flex; align-items: flex-start; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.day-name { width: 120px; padding-top: 8px; font-weight: 500; flex-shrink: 0; }
@media (max-width: 600px) { .day-row { flex-wrap: wrap; } .day-name { width: 100%; padding-top: 0; } }
</style>
