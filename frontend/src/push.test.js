import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api', () => ({ api: vi.fn() }))
vi.mock('./notifications', () => ({ refresh: vi.fn(async () => {}) }))
import { api } from './api'
import { refresh } from './notifications'
import { CHANNEL_ID, _resetForTests, safeLink, setupPush, unregisterDevice } from './push'

/** Plugin do Capacitor simulado: guarda os ouvintes para podermos "disparar" eventos do aparelho. */
function fakePlugin({ permission = 'granted', afterRequest = 'granted' } = {}) {
  const listeners = {}
  const plugin = {
    calls: [],
    createChannel: vi.fn(async (c) => { plugin.calls.push(['createChannel', c]) }),
    checkPermissions: vi.fn(async () => ({ receive: permission })),
    requestPermissions: vi.fn(async () => ({ receive: afterRequest })),
    addListener: vi.fn(async (name, fn) => { listeners[name] = fn; return { remove: vi.fn() } }),
    register: vi.fn(async () => { plugin.calls.push(['register']) }),
    emit: (name, payload) => listeners[name](payload),
  }
  return plugin
}
const router = () => ({ push: vi.fn() })
beforeEach(() => { api.mockReset(); api.mockResolvedValue({}); refresh.mockClear(); _resetForTests(); vi.spyOn(console, 'warn').mockImplementation(() => {}) })

describe('setupPush', () => {
  it('no navegador comum não faz nada', async () => {
    const plugin = fakePlugin()
    expect(await setupPush({ plugin, native: false })).toBe('skipped')
    expect(plugin.createChannel).not.toHaveBeenCalled(); expect(plugin.register).not.toHaveBeenCalled()
  })

  it('no app: cria o canal "avisos", confirma a permissão e registra, nessa ordem', async () => {
    const plugin = fakePlugin({ permission: 'granted' })
    expect(await setupPush({ plugin, native: true, router: router() })).toBe('ok')
    expect(plugin.calls.map(([n]) => n)).toEqual(['createChannel', 'register'])
    expect(plugin.calls[0][1]).toMatchObject({ id: CHANNEL_ID, name: 'Avisos', importance: 5 })
    expect(CHANNEL_ID).toBe('avisos')                                          // o servidor envia para este mesmo canal
    expect(plugin.requestPermissions).not.toHaveBeenCalled()                    // já tinha permissão: não pergunta de novo
  })

  it('Android 13+: pede a permissão quando ainda não foi decidida e registra se for concedida', async () => {
    const plugin = fakePlugin({ permission: 'prompt', afterRequest: 'granted' })
    expect(await setupPush({ plugin, native: true })).toBe('ok')
    expect(plugin.requestPermissions).toHaveBeenCalledOnce(); expect(plugin.register).toHaveBeenCalledOnce()
  })

  it('também pergunta quando o sistema pede para explicar antes ("prompt-with-rationale")', async () => {
    const plugin = fakePlugin({ permission: 'prompt-with-rationale', afterRequest: 'granted' })
    await setupPush({ plugin, native: true })
    expect(plugin.requestPermissions).toHaveBeenCalledOnce()
  })

  it.each([['denied', 'denied'], ['prompt', 'denied']])('permissão negada (%s -> %s): não registra e avisa que foi negado', async (before, after) => {
    const plugin = fakePlugin({ permission: before, afterRequest: after })
    expect(await setupPush({ plugin, native: true })).toBe('denied')
    expect(plugin.register).not.toHaveBeenCalled(); expect(api).not.toHaveBeenCalled()
  })

  it('se o plugin falhar, não derruba o app: devolve "error"', async () => {
    const plugin = fakePlugin()
    plugin.register.mockRejectedValue(new Error('Google Play Services ausente'))
    expect(await setupPush({ plugin, native: true })).toBe('error')
  })

  it('chamar duas vezes não cria ouvintes duplicados', async () => {
    const plugin = fakePlugin()
    await setupPush({ plugin, native: true }); await setupPush({ plugin, native: true })
    expect(plugin.addListener).toHaveBeenCalledTimes(4)                         // 4 eventos, uma única vez
    expect(plugin.register).toHaveBeenCalledTimes(2)
  })
})

describe('eventos do aparelho', () => {
  it('ao receber o token, envia ao servidor (somente o token e a plataforma)', async () => {
    const plugin = fakePlugin()
    await setupPush({ plugin, native: true })
    await plugin.emit('registration', { value: 'TOKEN-FCM-DO-APARELHO-1234567890' })
    expect(api).toHaveBeenCalledWith('/devices', { method: 'POST', body: { token: 'TOKEN-FCM-DO-APARELHO-1234567890', platform: 'android' } })
  })

  it('sem rede ao registrar não gera erro', async () => {
    const plugin = fakePlugin()
    await setupPush({ plugin, native: true })
    api.mockRejectedValue(new Error('sem rede'))
    await expect(plugin.emit('registration', { value: 'TOKEN-FCM-DO-APARELHO-1234567890' })).resolves.toBeUndefined()
  })

  it('push com o app aberto atualiza o sino', async () => {
    const plugin = fakePlugin()
    await setupPush({ plugin, native: true })
    plugin.emit('pushNotificationReceived', { title: 'x' })
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('tocar no aviso do sistema abre a tela indicada e atualiza o sino', async () => {
    const plugin = fakePlugin(), r = router()
    await setupPush({ plugin, native: true, router: r })
    plugin.emit('pushNotificationActionPerformed', { actionId: 'tap', notification: { data: { link: '/agendamentos', notification_id: '7' } } })
    expect(r.push).toHaveBeenCalledWith('/agendamentos'); expect(refresh).toHaveBeenCalled()
  })

  it('tocar num aviso sem link só atualiza o sino', async () => {
    const plugin = fakePlugin(), r = router()
    await setupPush({ plugin, native: true, router: r })
    plugin.emit('pushNotificationActionPerformed', { notification: { data: {} } })
    expect(r.push).not.toHaveBeenCalled(); expect(refresh).toHaveBeenCalled()
  })

  it.each(['//evil.com/x', 'https://evil.com', 'javascript:alert(1)', '/ok/../../x\n', 'agendamentos', '', null, 42, '/a b'])
  ('link perigoso "%s" nunca é aberto', async (bad) => {
    const plugin = fakePlugin(), r = router()
    await setupPush({ plugin, native: true, router: r })
    plugin.emit('pushNotificationActionPerformed', { notification: { data: { link: bad } } })
    expect(r.push).not.toHaveBeenCalled()
  })

  it('erro de registro só é anotado, sem quebrar', async () => {
    const plugin = fakePlugin()
    await setupPush({ plugin, native: true })
    expect(() => plugin.emit('registrationError', { error: 'SERVICE_NOT_AVAILABLE' })).not.toThrow()
  })
})

describe('safeLink', () => {
  it.each(['/agendamentos', '/usuarios', '/clientes?x=1', '/'])('aceita %s', (l) => expect(safeLink(l)).toBe(l))
})

describe('unregisterDevice', () => {
  it('ao sair, remove o token deste aparelho no servidor e esquece o token', async () => {
    const plugin = fakePlugin()
    await setupPush({ plugin, native: true })
    await plugin.emit('registration', { value: 'TOKEN-FCM-DO-APARELHO-1234567890' })
    api.mockClear()
    await unregisterDevice()
    expect(api).toHaveBeenCalledWith('/devices/remove', { method: 'POST', body: { token: 'TOKEN-FCM-DO-APARELHO-1234567890' } })
    api.mockClear(); await unregisterDevice()
    expect(api).not.toHaveBeenCalled()                                         // já removido: não repete
  })

  it('sem token registrado (ex.: navegador), não faz nada', async () => {
    await unregisterDevice()
    expect(api).not.toHaveBeenCalled()
  })

  it('se o servidor falhar ao remover, a saída continua normalmente', async () => {
    const plugin = fakePlugin()
    await setupPush({ plugin, native: true })
    await plugin.emit('registration', { value: 'TOKEN-FCM-DO-APARELHO-1234567890' })
    api.mockRejectedValue(new Error('sem rede'))
    await expect(unregisterDevice()).resolves.toBeUndefined()
  })
})

describe('endereço da API', () => {
  it('no app, VITE_API_URL vira o endereço base; no navegador continua relativo', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }))
    vi.stubGlobal('fetch', fetchMock)
    vi.doUnmock('./api')
    vi.resetModules()
    vi.stubEnv('VITE_API_URL', 'https://agenda.exemplo.com.br')
    const real = await import('./api?real')
    await real.api('/services')
    expect(String(fetchMock.mock.calls[0][0])).toBe('https://agenda.exemplo.com.br/api/v1/services')
    vi.stubEnv('VITE_API_URL', '')
    vi.resetModules()
    const web = await import('./api?web')
    await web.api('/services')
    expect(String(fetchMock.mock.calls[1][0])).toBe(`${window.location.origin}/api/v1/services`)
    vi.unstubAllEnvs(); vi.unstubAllGlobals()
  })
})
