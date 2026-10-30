<script setup>
// Atendimento: clientes que pediram para falar com uma pessoa. O dono abre o WhatsApp dela e, resolvido, marca como resolvido.
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { inbox } from '../notifications'
import { timeAgo } from '../utils/datetime'
import { formatPhone } from '../utils/format'
import { notify, notifyError } from '../utils/notify'
import { handoffMessage, whatsappLink } from '../utils/whatsapp'

const items = ref([])
const loading = ref(false)
const busy = ref(null)

async function load() {
  loading.value = true
  try { items.value = await api('/conversations') }
  catch (e) { notifyError(e) }
  finally { loading.value = false }
}
onMounted(load)
// Chegou um aviso novo no sino (ex.: outra cliente pediu atendimento): atualiza a lista.
watch(() => inbox.items[0]?.id, (id, old) => { if (old !== undefined && id !== old) load() })

const linkFor = (c) => whatsappLink(c.client_phone, handoffMessage(c.client_name))
const channelName = (c) => c.channel.charAt(0).toUpperCase() + c.channel.slice(1)

async function resolve(c) {
  busy.value = c.id
  try {
    await api(`/conversations/${c.id}/resolve`, { method: 'POST' })
    items.value = items.value.filter((x) => x.id !== c.id)
    notify('Marcado como resolvido')
  } catch (e) { notifyError(e) }
  finally { busy.value = null }
}
</script>

<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-6">
    <div class="mr-auto">
      <div class="eyebrow mb-1">Clientes que pediram para falar com você</div>
      <h1 class="page-title">Atendimento</h1>
    </div>
    <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="load">Atualizar</v-btn>
  </div>

  <div v-if="!items.length && !loading" class="empty">
    <v-icon icon="mdi-check-circle-outline" size="44" />
    <div class="mt-2">Ninguém esperando por você. Tudo em dia!</div>
  </div>

  <v-card v-for="c in items" :key="c.id" class="wait mb-3">
    <div class="top">
      <div class="info">
        <div class="d-flex flex-wrap align-center ga-2">
          <span class="name">{{ c.client_name || 'Cliente ainda sem cadastro' }}</span>
          <v-chip size="small" variant="tonal">{{ channelName(c) }}</v-chip>
        </div>
        <div v-if="c.client_phone" class="phone num">{{ formatPhone(c.client_phone) }}</div>
        <div v-else class="phone">Ainda não informou o celular</div>
        <div v-if="c.handoff_note" class="note">“{{ c.handoff_note }}”</div>
      </div>
      <div class="since">esperando {{ c.handoff_at ? timeAgo(c.handoff_at).replace('há ', '') : '' }}</div>
    </div>
    <div class="actions">
      <v-btn v-if="linkFor(c)" :href="linkFor(c)" target="_blank" rel="noopener noreferrer" color="success" variant="flat" size="small"
             prepend-icon="mdi-whatsapp">Abrir WhatsApp</v-btn>
      <span v-else class="text-body-small text-medium-emphasis">Sem WhatsApp para responder (a cliente ainda não informou o celular).</span>
      <v-spacer />
      <v-btn variant="text" size="small" prepend-icon="mdi-check" :loading="busy === c.id" @click="resolve(c)">Marcar como resolvido</v-btn>
    </div>
  </v-card>
</template>

<style scoped>
.wait { padding: 16px 18px; border-left: 5px solid rgb(var(--v-theme-warning)); }
.top { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap; }
.name { font-weight: 600; font-size: 1.02rem; }
.phone { font-size: 0.85rem; opacity: 0.7; margin-top: 2px; }
.note { margin-top: 8px; font-size: 0.9rem; font-style: italic; }
.since { font-size: 0.78rem; opacity: 0.6; white-space: nowrap; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.empty { text-align: center; padding: 56px 16px; opacity: 0.7; }
</style>
