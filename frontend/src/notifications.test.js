import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api', () => ({ api: vi.fn() }))
vi.mock('./utils/notify', () => ({ notify: vi.fn() }))
import { api } from './api'
import { inbox, markAllRead, markRead, refresh, resetInbox, startPolling, stopPolling } from './notifications'
import { notify } from './utils/notify'

const n = (id, over = {}) => ({ id, kind: 'appointment_cancelled', title: 'Agendamento cancelado', body: `corpo ${id}`, link: '/agendamentos', created_at: '2029-03-10T12:00:00Z', read_at: null, ...over })
const serve = (items, unread = items.length) => api.mockImplementation(async (path, opts = {}) => {
  if (path === '/notifications') return { items, unread_count: unread }
  return {}
})
beforeEach(() => { api.mockReset(); notify.mockReset(); resetInbox() })
afterEach(() => { resetInbox(); vi.useRealTimers() })

describe('refresh', () => {
  it('a primeira carga mostra o sino mas NÃO dispara avisos na tela (são antigos)', async () => {
    serve([n(3), n(2), n(1)])
    await refresh()
    expect(inbox.items).toHaveLength(3); expect(inbox.unread).toBe(3); expect(inbox.loaded).toBe(true)
    expect(notify).not.toHaveBeenCalled()
  })

  it('um aviso novo depois da primeira carga aparece na tela uma única vez', async () => {
    serve([n(2), n(1)]); await refresh()
    serve([n(3, { body: 'Maria cancelou' }), n(2), n(1)]); await refresh()
    expect(notify).toHaveBeenCalledTimes(1)
    expect(notify).toHaveBeenCalledWith('Agendamento cancelado: Maria cancelou', 'warning')
    await refresh()                                                          // mesma lista: nada novo
    expect(notify).toHaveBeenCalledTimes(1)
  })

  it('cancelamento sai como alerta; os demais como informação', async () => {
    serve([n(1)]); await refresh()
    serve([n(3, { kind: 'appointment_booked', title: 'Novo agendamento' }), n(2), n(1)]); await refresh()
    expect(notify).toHaveBeenCalledWith(expect.stringContaining('Novo agendamento'), 'info')
  })

  it('se chegarem muitos de uma vez, só os 3 mais recentes viram aviso na tela (em ordem cronológica)', async () => {
    serve([n(1)]); await refresh()
    serve([n(6), n(5), n(4), n(3), n(2), n(1)]); await refresh()
    expect(notify.mock.calls.map(([t]) => t)).toEqual(['Agendamento cancelado: corpo 4', 'Agendamento cancelado: corpo 5', 'Agendamento cancelado: corpo 6'])
    expect(inbox.unread).toBe(6)                                             // o sino mostra tudo
  })

  it('lista vazia funciona', async () => {
    serve([], 0); await refresh()
    expect(inbox.items).toEqual([]); expect(inbox.unread).toBe(0)
  })

  it('o aviso do sistema só sai com permissão concedida e a aba escondida', async () => {
    const shown = []
    globalThis.Notification = class { constructor(title, opts) { shown.push([title, opts.body]) } }
    globalThis.Notification.permission = 'granted'
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    serve([n(1)]); await refresh()
    serve([n(2, { body: 'novo' }), n(1)]); await refresh()
    expect(shown).toEqual([['Agendamento cancelado', 'novo']])

    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
    serve([n(3), n(2), n(1)]); await refresh()
    expect(shown).toHaveLength(1)                                            // aba à vista: já aparece na tela, sem duplicar no sistema
    globalThis.Notification.permission = 'denied'
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    serve([n(4), n(3), n(2), n(1)]); await refresh()
    expect(shown).toHaveLength(1)
    delete globalThis.Notification
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })
})

describe('marcar como lida', () => {
  it('uma: atualiza na hora e chama a API', async () => {
    serve([n(2), n(1)]); await refresh()
    await markRead(inbox.items[0])
    expect(inbox.items[0].read_at).toBeTruthy(); expect(inbox.unread).toBe(1)
    expect(api).toHaveBeenCalledWith('/notifications/2/read', { method: 'POST' })
  })

  it('já lida: não chama a API de novo', async () => {
    serve([n(1, { read_at: '2029-03-10T12:30:00Z' })], 0); await refresh()
    api.mockClear()
    await markRead(inbox.items[0])
    expect(api).not.toHaveBeenCalled()
  })

  it('se a API falhar, desfaz e o contador volta', async () => {
    serve([n(1)]); await refresh()
    api.mockRejectedValue(new Error('sem rede'))
    await markRead(inbox.items[0])
    expect(inbox.items[0].read_at).toBeNull(); expect(inbox.unread).toBe(1)
  })

  it('todas: zera o contador e, se falhar, restaura exatamente como estava', async () => {
    serve([n(3), n(2, { read_at: '2029-03-10T12:30:00Z' }), n(1)], 2); await refresh()
    api.mockRejectedValue(new Error('sem rede'))
    await markAllRead()
    expect(inbox.unread).toBe(2); expect(inbox.items.map((i) => i.read_at)).toEqual([null, '2029-03-10T12:30:00Z', null])
    serve([n(3), n(2), n(1)]); api.mockImplementation(async () => ({ updated: 3 }))
    await markAllRead()
    expect(inbox.unread).toBe(0); expect(inbox.items.every((i) => i.read_at)).toBe(true)
  })
})

describe('polling', () => {
  it('busca a cada 20 s com o painel à vista e para ao parar', async () => {
    vi.useFakeTimers()
    serve([n(1)])
    startPolling(); await vi.advanceTimersByTimeAsync(0)
    expect(api.mock.calls.filter(([p]) => p === '/notifications')).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(20_000)
    expect(api.mock.calls.filter(([p]) => p === '/notifications')).toHaveLength(2)
    stopPolling()
    await vi.advanceTimersByTimeAsync(120_000)
    expect(api.mock.calls.filter(([p]) => p === '/notifications')).toHaveLength(2)
  })

  it('iniciar duas vezes não cria dois ciclos', async () => {
    vi.useFakeTimers()
    serve([])
    startPolling(); startPolling(); await vi.advanceTimersByTimeAsync(0)
    expect(api.mock.calls).toHaveLength(1)
  })

  it('uma falha de rede não derruba o ciclo: o próximo ciclo recupera', async () => {
    vi.useFakeTimers()
    api.mockRejectedValueOnce(new Error('sem rede'))                         // 1ª tentativa falha
    api.mockImplementation(async () => ({ items: [n(1)], unread_count: 1 }))  // as seguintes funcionam
    startPolling(); await vi.advanceTimersByTimeAsync(0)
    expect(inbox.loaded).toBe(false)                                         // a falha não derrubou nem carregou nada
    await vi.advanceTimersByTimeAsync(20_000)
    expect(inbox.items).toHaveLength(1); expect(inbox.unread).toBe(1)
  })

  it('com a aba escondida o intervalo sobe para 60 s', async () => {
    vi.useFakeTimers()
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    serve([])
    startPolling(); await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(api.mock.calls).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(31_000)
    expect(api.mock.calls).toHaveLength(2)
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })

  it('resetInbox limpa tudo para a próxima pessoa que entrar', async () => {
    serve([n(1)]); await refresh()
    resetInbox()
    expect(inbox.items).toEqual([]); expect(inbox.unread).toBe(0); expect(inbox.loaded).toBe(false)
    serve([n(1)]); await refresh()
    expect(notify).not.toHaveBeenCalled()                                    // volta a ser "primeira carga": sem avisos antigos
  })
})
