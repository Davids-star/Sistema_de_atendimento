import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

vi.mock('../api', () => ({ api: vi.fn() }))
import { api } from '../api'
import { inbox, resetInbox } from '../notifications'
import { bodyText, mountView, norm } from '../test-helpers'
import NotificationBell from './NotificationBell.vue'

const item = (id, over = {}) => ({ id, kind: 'appointment_cancelled', title: 'Agendamento cancelado', body: `Maria · Manicure #${id}`,
  link: '/agendamentos', created_at: new Date(Date.now() - 5 * 60000).toISOString(), read_at: null, ...over })
const makeRouter = () => createRouter({ history: createMemoryHistory(), routes: [
  { path: '/', component: { template: '<i/>' } }, { path: '/agendamentos', component: { template: '<i/>' } }, { path: '/usuarios', component: { template: '<i/>' } }] })
const load = (items, unread = items.filter((i) => !i.read_at).length) => { inbox.items = items; inbox.unread = unread; inbox.loaded = true }
const open = async (router = makeRouter()) => {
  const w = await mountView(NotificationBell, {}, [router])
  document.querySelector('button[aria-label="Notificações"]').click(); await flushPromises()
  return { w, router }
}
beforeEach(() => { api.mockReset(); api.mockResolvedValue({}); resetInbox(); document.body.innerHTML = ''; delete globalThis.Notification })

describe('NotificationBell', () => {
  it('mostra o número de não lidas no sino, e some quando zera', async () => {
    load([item(2), item(1)])
    const w = await mountView(NotificationBell, {}, [makeRouter()])
    expect(norm(w.find('.v-badge__badge').text())).toBe('2')
    load([item(2, { read_at: 'x' })], 0); await flushPromises()
    expect(w.find('.v-badge__badge').exists() && w.find('.v-badge__badge').isVisible()).toBe(false)
  })

  it('mais de 99 vira "99+"', async () => {
    load([item(1)], 150)
    expect(norm((await mountView(NotificationBell, {}, [makeRouter()])).find('.v-badge__badge').text())).toBe('99+')
  })

  it('a lista traz título, texto, tempo e destaca só as não lidas', async () => {
    load([item(2), item(1, { read_at: new Date().toISOString() })])
    await open()
    const t = bodyText()
    expect(t).toContain('Agendamento cancelado'); expect(t).toContain('Maria · Manicure #2'); expect(t).toContain('há 5 min')
    const rows = [...document.querySelectorAll('.bell-card .v-list-item')]
    expect(rows).toHaveLength(2)
    expect(rows[0].classList.contains('unread')).toBe(true); expect(rows[1].classList.contains('unread')).toBe(false)
    expect(document.querySelectorAll('.bell-card .dot')).toHaveLength(1)
  })

  it('sem avisos mostra a mensagem de vazio e desabilita "marcar todas"', async () => {
    load([], 0)
    await open()
    expect(bodyText()).toContain('Nenhuma notificação por enquanto')
    const all = [...document.querySelectorAll('.bell-card button')].find((b) => norm(b.textContent) === 'Marcar todas como lidas')
    expect(all.disabled).toBe(true)
  })

  it('tocar num aviso marca como lido e abre a tela dele', async () => {
    load([item(7, { link: '/usuarios', kind: 'user_signup', title: 'Novo cadastro' })])
    const { router } = await open()
    document.querySelector('.bell-card .v-list-item').click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/notifications/7/read', { method: 'POST' })
    expect(inbox.unread).toBe(0)
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/usuarios'))   // a navegação do roteador é assíncrona
  })

  it('aviso sem link só marca como lido', async () => {
    load([item(8, { link: null })])
    const { router } = await open()
    await router.push('/'); document.querySelector('.bell-card .v-list-item').click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/notifications/8/read', { method: 'POST' })
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('"Marcar todas como lidas" zera o contador', async () => {
    load([item(2), item(1)])
    await open()
    ;[...document.querySelectorAll('.bell-card button')].find((b) => norm(b.textContent) === 'Marcar todas como lidas').click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/notifications/read-all', { method: 'POST' })
    expect(inbox.unread).toBe(0)
  })

  it('oferece ativar os avisos do sistema só quando o navegador ainda não decidiu', async () => {
    globalThis.Notification = Object.assign(vi.fn(), { permission: 'default', requestPermission: vi.fn(async () => 'granted') })
    load([item(1)])
    await open()
    expect(bodyText()).toContain('Receber avisos mesmo com o painel em segundo plano?')
    ;[...document.querySelectorAll('.bell-card button')].find((b) => norm(b.textContent) === 'Ativar avisos').click(); await flushPromises()
    expect(globalThis.Notification.requestPermission).toHaveBeenCalledOnce()
    expect(bodyText()).not.toContain('Receber avisos mesmo com o painel')                  // depois de decidir, o convite some
  })

  it.each(['granted', 'denied'])('não oferece quando a permissão já é %s', async (permission) => {
    globalThis.Notification = Object.assign(vi.fn(), { permission })
    load([item(1)])
    await open()
    expect(bodyText()).not.toContain('Ativar avisos')
  })

  it('sem suporte a notificações do navegador, não mostra o convite', async () => {
    load([item(1)])
    await open()
    expect(bodyText()).not.toContain('Ativar avisos')
  })

  it('aviso de pedido de atendimento tem o ícone de mensagem e abre a tela Atendimento', async () => {
    const r = makeRouter(); r.addRoute({ path: '/atendimento', component: { template: '<i/>' } })
    load([item(5, { kind: 'handoff', title: 'Cliente quer falar com você', link: '/atendimento' })])
    await open(r)
    expect(document.querySelector('.bell-card .mdi-message-alert-outline')).not.toBeNull()
    document.querySelector('.bell-card .v-list-item').click(); await flushPromises()
    await vi.waitFor(() => expect(r.currentRoute.value.path).toBe('/atendimento'))
  })
})
