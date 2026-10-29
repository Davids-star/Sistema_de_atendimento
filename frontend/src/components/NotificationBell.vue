<script setup>
// Sino de notificações: contador, lista dos avisos e "marcar como lida". Ao tocar num aviso, abre a tela relacionada.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { askOsPermission, inbox, markAllRead, markRead } from '../notifications'
import { timeAgo } from '../utils/datetime'

const router = useRouter()
const open = ref(false)
const osPermission = ref(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission)

const ICON = { appointment_cancelled: 'mdi-calendar-remove-outline', appointment_booked: 'mdi-calendar-plus', user_signup: 'mdi-account-clock-outline' }
const COLOR = { appointment_cancelled: 'error', appointment_booked: 'success', user_signup: 'warning' }
const badge = computed(() => (inbox.unread > 99 ? '99+' : inbox.unread))

async function openItem(item) {
  open.value = false
  await markRead(item)
  if (item.link) router.push(item.link)
}
async function enableOs() { osPermission.value = await askOsPermission() }
</script>

<template>
  <v-menu v-model="open" :close-on-content-click="false" location="bottom end" max-width="380">
    <template #activator="{ props }">
      <v-btn v-bind="props" variant="text" icon aria-label="Notificações" :title="inbox.unread ? `${inbox.unread} não lida(s)` : 'Notificações'">
        <v-badge :content="badge" color="error" :model-value="inbox.unread > 0" floating>
          <v-icon icon="mdi-bell-outline" />
        </v-badge>
      </v-btn>
    </template>

    <v-card class="bell-card" min-width="320">
      <div class="head">
        <span class="section-title">Notificações</span>
        <v-btn size="x-small" variant="text" :disabled="!inbox.unread" @click="markAllRead">Marcar todas como lidas</v-btn>
      </div>
      <v-divider />

      <div v-if="!inbox.items.length" class="empty">
        <v-icon icon="mdi-bell-check-outline" size="32" />
        <div class="mt-1">Nenhuma notificação por enquanto.</div>
      </div>

      <v-list v-else lines="three" class="list" density="comfortable">
        <v-list-item v-for="n in inbox.items" :key="n.id" :class="{ unread: !n.read_at }" @click="openItem(n)">
          <template #prepend>
            <v-avatar :color="COLOR[n.kind] || 'primary'" variant="tonal" size="36"><v-icon :icon="ICON[n.kind] || 'mdi-bell-outline'" size="20" /></v-avatar>
          </template>
          <v-list-item-title class="item-title">{{ n.title }}</v-list-item-title>
          <v-list-item-subtitle class="item-body">{{ n.body }}</v-list-item-subtitle>
          <div class="when">{{ timeAgo(n.created_at) }}</div>
          <template v-if="!n.read_at" #append><span class="dot" aria-label="não lida" /></template>
        </v-list-item>
      </v-list>

      <template v-if="osPermission === 'default'">
        <v-divider />
        <div class="foot">
          <span>Receber avisos mesmo com o painel em segundo plano?</span>
          <v-btn size="x-small" color="primary" variant="tonal" @click="enableOs">Ativar avisos</v-btn>
        </div>
      </template>
    </v-card>
  </v-menu>
</template>

<style scoped>
.bell-card { overflow: hidden; }
.head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; }
.list { max-height: 380px; overflow-y: auto; padding: 0; }
.empty { text-align: center; padding: 28px 16px; opacity: 0.65; font-size: 0.9rem; }
.unread { background: rgba(var(--v-theme-primary), 0.06); }
.item-title { font-weight: 600; font-size: 0.9rem; white-space: normal; }
.item-body { white-space: normal; font-size: 0.8rem; opacity: 0.85; -webkit-line-clamp: 3; }
.when { font-size: 0.72rem; opacity: 0.55; margin-top: 2px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: rgb(var(--v-theme-error)); display: inline-block; }
.foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px; font-size: 0.78rem; }
</style>
