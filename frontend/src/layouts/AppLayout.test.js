import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

vi.mock('../api', () => ({ api: vi.fn(), setToken: vi.fn() }))
vi.mock('../push', () => ({ setupPush: vi.fn(), unregisterDevice: vi.fn(async () => {}) }))
import { api } from '../api'
import { inbox, resetInbox, stopPolling } from '../notifications'
import { resetSession, session } from '../session'
import { mountView, norm } from '../test-helpers'
import AppLayout from './AppLayout.vue'

const names = ['dashboard', 'appointments', 'handoff', 'services', 'clients', 'users', 'settings']
const makeRouter = () => createRouter({ history: createMemoryHistory(), routes: names.map((n) => ({ path: `/${n}`, name: n, component: { template: '<i/>' } })) })
const user = (over) => ({ id: 1, name: 'Ana', approved: true, is_owner: true, phone: '5511999990000', ...over })
const open = async (u, notes = []) => {
  session.user = u; session.loaded = true
  api.mockImplementation(async (path) => (path === '/notifications' ? { items: notes, unread_count: notes.length } : path === '/users' ? [{ id: 5 }, { id: 6 }] : u))
  const r = makeRouter(); await r.push('/dashboard')
  const w = await mountView(AppLayout, {}, [r])
  await flushPromises()
  return w
}
const titles = () => [...document.querySelectorAll('.sidebar .v-list-item-title')].map((e) => norm(e.textContent))
beforeEach(() => { api.mockReset(); resetInbox(); resetSession(); document.body.innerHTML = '' })

describe('AppLayout: menu lateral', () => {
  it('mostra somente o primeiro nome no cabeçalho', async () => {
    const w = await open(user({ name: 'Ana Maria Silva' }))
    expect(norm(w.find('.user-name').text())).toBe('Ana')
    stopPolling()
  })

  it('mantém a navegação do computador expandida sem botão hambúrguer', async () => {
    await open(user())
    expect(document.querySelector('.sidebar')).not.toBeNull()
    expect(document.querySelector('.sidebar.v-navigation-drawer--rail')).toBeNull()
    expect(document.querySelector('.menu-toggle')).toBeNull()
    stopPolling()
  })

  it('mostra todas as telas do dono, incluindo Atendimento', async () => {
    await open(user())
    expect(titles()).toEqual(['Dashboard', 'Agendamentos', 'Atendimento', 'Serviços', 'Clientes', 'Usuários', 'Configurações'])
    stopPolling()
  })

  it('quem não é dono não vê Usuários, mas vê Atendimento', async () => {
    await open(user({ is_owner: false }))
    expect(titles()).toContain('Atendimento'); expect(titles()).not.toContain('Usuários')
    stopPolling()
  })

  it('o item Atendimento mostra quantos pedidos não lidos existem', async () => {
    const note = (id, kind, read_at = null) => ({ id, kind, title: 't', body: 'b', link: '/x', created_at: new Date().toISOString(), read_at })
    await open(user(), [note(3, 'handoff'), note(2, 'handoff'), note(1, 'handoff', 'x'), note(4, 'appointment_cancelled')])
    const item = [...document.querySelectorAll('.sidebar .v-list-item')].find((i) => norm(i.textContent).startsWith('Atendimento'))
    expect(norm(item.querySelector('.nav-badge').textContent)).toBe('2')           // só os "handoff" NÃO lidos
    stopPolling()
  })

  it('sem pedidos pendentes não mostra contador', async () => {
    await open(user())
    const item = [...document.querySelectorAll('.sidebar .v-list-item')].find((i) => norm(i.textContent).startsWith('Atendimento'))
    expect(item.querySelector('.nav-badge')).toBeNull()
    stopPolling()
  })

  it('o contador de Usuários continua só para o dono', async () => {
    await open(user())
    const item = [...document.querySelectorAll('.sidebar .v-list-item')].find((i) => norm(i.textContent).startsWith('Usuários'))
    expect(norm(item.querySelector('.nav-badge').textContent)).toBe('2')
    stopPolling()
  })

  it('o pop-up do perfil abre ao clicar no usuário e contém opção de foto e configurações', async () => {
    const w = await open(user({ name: 'Felipe Davids', email: 'felipe@teste.com' }))
    const btn = w.find('.user-heading-btn')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    await flushPromises()
    const popup = document.querySelector('.user-popup-card')
    expect(popup).not.toBeNull()
    const text = norm(popup.textContent)
    expect(text).toContain('Felipe Davids')
    expect(text).toContain('felipe@teste.com')
    expect(text).toContain('foto de perfil')
    expect(text).toContain('Configurações')
    stopPolling()
  })
})
