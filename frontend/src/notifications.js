// Central de notificações do painel: busca os avisos, detecta os novos e avisa na tela (e no sistema, se permitido).
import { reactive } from 'vue'
import { api } from './api'
import { notify } from './utils/notify'

export const inbox = reactive({ items: [], unread: 0, loaded: false })

const VISIBLE_MS = 20_000   // com o painel aberto
const HIDDEN_MS = 60_000    // aba em segundo plano
let timer = null
let running = false
let lastSeenId = 0

const isHidden = () => typeof document !== 'undefined' && document.hidden

// Aviso do sistema operacional (fora do app Capacitor): só se a pessoa permitiu e a aba não está à vista.
function osNotification(item) {
  try {
    if (typeof Notification !== 'undefined' && Notification.permission === 'granted' && isHidden()) {
      new Notification(item.title, { body: item.body, tag: `n${item.id}` })
    }
  } catch { /* alguns navegadores móveis só permitem via service worker */ }
}

export async function refresh() {
  const data = await api('/notifications', { params: { limit: 20 } })
  const firstLoad = !inbox.loaded
  const fresh = data.items.filter((n) => n.id > lastSeenId)
  if (!firstLoad) {
    // Mostra no máximo 3 de uma vez (se chegaram muitos, o sino mostra o resto).
    fresh.slice(0, 3).reverse().forEach((n) => { notify(`${n.title}: ${n.body}`, n.kind === 'appointment_cancelled' ? 'warning' : 'info'); osNotification(n) })
  }
  if (data.items.length) lastSeenId = Math.max(lastSeenId, data.items[0].id)
  inbox.items = data.items
  inbox.unread = data.unread_count
  inbox.loaded = true
}

async function loop() {
  if (!running) return
  try { await refresh() } catch { /* sem rede ou sessão vencida: tenta de novo no próximo ciclo */ }
  if (running) timer = setTimeout(loop, isHidden() ? HIDDEN_MS : VISIBLE_MS)
}

const onVisible = () => { if (!document.hidden && running) { clearTimeout(timer); loop() } }   // voltou para o app: atualiza já

export function startPolling() {
  if (running) return
  running = true
  document.addEventListener('visibilitychange', onVisible)
  loop()
}

export function stopPolling() {
  running = false
  clearTimeout(timer)
  document.removeEventListener('visibilitychange', onVisible)
}

export function resetInbox() {
  stopPolling()
  inbox.items = []; inbox.unread = 0; inbox.loaded = false
  lastSeenId = 0
}

export async function markRead(item) {
  if (item.read_at) return
  item.read_at = new Date().toISOString()      // atualiza na hora; se a API falhar, desfaz
  inbox.unread = Math.max(0, inbox.unread - 1)
  try { await api(`/notifications/${item.id}/read`, { method: 'POST' }) }
  catch { item.read_at = null; inbox.unread += 1 }
}

export async function markAllRead() {
  const before = inbox.items.map((n) => n.read_at)
  const unread = inbox.unread
  const now = new Date().toISOString()
  inbox.items.forEach((n) => { n.read_at ??= now })
  inbox.unread = 0
  try { await api('/notifications/read-all', { method: 'POST' }) }
  catch { inbox.items.forEach((n, i) => { n.read_at = before[i] }); inbox.unread = unread }
}

export function askOsPermission() {
  if (typeof Notification === 'undefined') return Promise.resolve('unsupported')
  return Notification.requestPermission()
}
