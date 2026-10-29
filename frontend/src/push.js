// Push no app Android (Capacitor + Firebase). No navegador comum não faz nada.
// Fluxo: cria o canal "avisos" -> pede permissão (Android 13+) -> registra no Firebase -> manda o token ao servidor.
import { Capacitor } from '@capacitor/core'
import { PushNotifications } from '@capacitor/push-notifications'
import { api } from './api'
import { refresh } from './notifications'

export const CHANNEL_ID = 'avisos'   // o servidor envia para este mesmo canal (senão o Android usa o canal padrão)

let currentToken = null
let listening = false

// Só aceita caminhos internos do painel (começam com "/", nunca "//" nem endereços externos).
export const safeLink = (link) => (typeof link === 'string' && /^\/(?!\/)[\w\-\/?=&%.]*$/.test(link) ? link : null)

export async function setupPush({ router, plugin = PushNotifications, native = Capacitor.isNativePlatform() } = {}) {
  if (!native) return 'skipped'
  try {
    await plugin.createChannel({ id: CHANNEL_ID, name: 'Avisos', description: 'Cancelamentos, novos agendamentos e cadastros', importance: 5, visibility: 1 })

    let { receive } = await plugin.checkPermissions()
    if (receive === 'prompt' || receive === 'prompt-with-rationale') ({ receive } = await plugin.requestPermissions())
    if (receive !== 'granted') return 'denied'

    if (!listening) {
      listening = true
      await plugin.addListener('registration', async (token) => {
        currentToken = token.value
        try { await api('/devices', { method: 'POST', body: { token: token.value, platform: 'android' } }) }
        catch { /* sem rede agora: o app registra de novo na próxima abertura */ }
      })
      await plugin.addListener('registrationError', (e) => console.warn('Falha ao registrar o push:', e?.error))
      await plugin.addListener('pushNotificationReceived', () => { refresh().catch(() => {}) })   // app aberto: atualiza o sino
      await plugin.addListener('pushNotificationActionPerformed', (action) => {                    // tocou no aviso do sistema
        refresh().catch(() => {})
        const link = safeLink(action?.notification?.data?.link)
        if (link && router) router.push(link)
      })
    }
    await plugin.register()
    return 'ok'
  } catch (e) {
    console.warn('Push indisponível:', e?.message)
    return 'error'
  }
}

// Ao sair: este aparelho deixa de receber os avisos desta conta. Deve rodar ANTES de apagar o login.
export async function unregisterDevice() {
  if (!currentToken) return
  const token = currentToken
  currentToken = null
  try { await api('/devices/remove', { method: 'POST', body: { token } }) } catch { /* se falhar, o servidor limpa o token quando ele deixar de valer */ }
}

export const _resetForTests = () => { currentToken = null; listening = false }
