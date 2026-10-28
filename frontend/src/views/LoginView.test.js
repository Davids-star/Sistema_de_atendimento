import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

vi.mock('../api', () => ({ api: vi.fn(), setToken: vi.fn() }))
vi.mock('../utils/google', () => ({ renderGoogleButton: vi.fn() }))
import { api, setToken } from '../api'
import { bodyText, mountView, typeInto } from '../test-helpers'
import { renderGoogleButton } from '../utils/google'
import LoginView from './LoginView.vue'

const router = () => createRouter({ history: createMemoryHistory(), routes: [
  { path: '/login', name: 'login', component: { template: '<i/>' } },
  { path: '/', name: 'dashboard', component: { template: '<i/>' } },
  { path: '/esqueci-senha', name: 'forgot', component: { template: '<i/>' } },
] })
const mountLogin = (r = router()) => mountView(LoginView, {}, [r])
const configWith = (id) => api.mockImplementation(async (path) => (path === '/auth/config' ? { google_client_id: id } : {}))

beforeEach(() => { api.mockReset(); setToken.mockReset(); renderGoogleButton.mockReset(); document.body.innerHTML = '' })

describe('LoginView com Google', () => {
  it('mostra o botão do Google quando o servidor tem o login configurado', async () => {
    configWith('abc.apps.googleusercontent.com')
    await mountLogin()
    expect(renderGoogleButton).toHaveBeenCalledOnce()
    expect(renderGoogleButton.mock.calls[0][1]).toBe('abc.apps.googleusercontent.com')
    expect(bodyText()).toContain('ou entre com e-mail')
  })

  it('sem configuração, mostra só o login por senha', async () => {
    configWith(null)
    await mountLogin()
    expect(renderGoogleButton).not.toHaveBeenCalled()
    expect(bodyText()).not.toContain('ou entre com e-mail')
    expect(bodyText()).toContain('Entrar')
  })

  it('se o Google não carregar, o login por senha continua disponível', async () => {
    configWith('abc')
    renderGoogleButton.mockRejectedValue(new Error('bloqueado'))
    await mountLogin()
    expect(bodyText()).not.toContain('ou entre com e-mail')
    expect(document.querySelector('input[type="email"]')).not.toBeNull()
  })

  it('envia o token do Google ao backend e entra', async () => {
    configWith('abc')
    api.mockImplementation(async (path, o = {}) => {
      if (path === '/auth/config') return { google_client_id: 'abc' }
      if (path === '/auth/google') return { access_token: 'jwt-123' }
    })
    const r = router(); await r.push('/login')
    await mountLogin(r)
    const onCredential = renderGoogleButton.mock.calls[0][2]
    await onCredential('token-do-google'); await flushPromises()
    expect(api).toHaveBeenCalledWith('/auth/google', { method: 'POST', body: { credential: 'token-do-google' } })
    expect(setToken).toHaveBeenCalledWith('jwt-123')
    expect(r.currentRoute.value.name).toBe('dashboard')
  })

  it('conta Google sem acesso mostra a mensagem do servidor', async () => {
    api.mockImplementation(async (path) => {
      if (path === '/auth/config') return { google_client_id: 'abc' }
      throw Object.assign(new Error('Esta conta Google não tem acesso ao painel'), { status: 401 })
    })
    await mountLogin()
    await renderGoogleButton.mock.calls[0][2]('x'); await flushPromises()
    expect(bodyText()).toContain('Esta conta Google não tem acesso ao painel')
    expect(setToken).not.toHaveBeenCalled()
  })
})

describe('LoginView com senha', () => {
  it('tem o link "Esqueci minha senha"', async () => {
    configWith(null)
    await mountLogin()
    expect(bodyText()).toContain('Esqueci minha senha')
    expect(document.querySelector('a[href="/esqueci-senha"]')).not.toBeNull()
  })

  it('senha errada mostra mensagem amigável', async () => {
    api.mockImplementation(async (path) => {
      if (path === '/auth/config') return { google_client_id: null }
      throw Object.assign(new Error('E-mail ou senha incorretos'), { status: 401 })
    })
    await mountLogin()
    await typeInto(document.querySelector('input[type="email"]'), 'a@b.com')
    await typeInto(document.querySelector('input[type="password"]'), 'errada')
    ;[...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Entrar').click()
    await flushPromises()
    expect(bodyText()).toContain('E-mail ou senha incorretos.')
  })
})
