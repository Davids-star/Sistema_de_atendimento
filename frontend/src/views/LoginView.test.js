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
    expect(document.querySelector('.google-btn')).not.toBeNull()
  })

  it('sem configuração, mostra só o login por senha', async () => {
    configWith(null)
    await mountLogin()
    expect(renderGoogleButton).not.toHaveBeenCalled()
    expect(document.querySelector('.google-btn')).toBeNull()
    expect(bodyText()).toContain('Entrar')
  })

  it('se o Google não carregar, o login por senha continua disponível', async () => {
    configWith('abc')
    renderGoogleButton.mockRejectedValue(new Error('bloqueado'))
    await mountLogin()
    expect(document.querySelector('.google-btn')).toBeNull()
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
    document.querySelector('form button[type="submit"]').click()
    await flushPromises()
    expect(bodyText()).toContain('E-mail ou senha incorretos.')
  })
})

describe('LoginView: criar conta e e-mail não confirmado', () => {
  const field = (label) => [...document.querySelectorAll('.v-field')].find((f) => f.textContent.includes(label))?.querySelector('input')
  const tab = (text) => [...document.querySelectorAll('[role="tab"]')].find((t) => t.textContent.trim() === text)
  const fillSignup = async (over = {}) => {
    const v = { Nome: 'Maria Souza', Celular: '(11) 98888-7777', 'E-mail': 'maria@gmail.com', Senha: 'uma-senha-forte-1', Repita: 'uma-senha-forte-1', ...over }
    const signupPanel = document.querySelectorAll('form')[1]
    const inputs = [...signupPanel.querySelectorAll('input')]
    for (const [i, key] of ['Nome', 'Celular', 'E-mail', 'Senha', 'Repita'].entries()) await typeInto(inputs[i], v[key])
    return signupPanel
  }
  const submitBtn = (panel) => panel.querySelector('button[type="submit"]')

  it('as duas abas existem e o botão de criar conta só habilita com tudo válido', async () => {
    configWith(null)
    await mountLogin()
    expect(tab('Entrar')).toBeTruthy(); expect(tab('Criar conta')).toBeTruthy()
    const panel = await fillSignup({ Celular: '123' })
    expect(submitBtn(panel).disabled).toBe(true)                       // celular inválido
    await fillSignup({ Repita: 'diferente-123456' })
    expect(submitBtn(panel).disabled).toBe(true)                       // confirmação diferente
    await fillSignup()
    expect(submitBtn(panel).disabled).toBe(false)
  })

  it('avisa, antes de criar a conta, que IP e localização são registrados e enviados ao dono', async () => {
    configWith(null)
    await mountLogin()
    const panel = document.querySelectorAll('form')[1]
    expect(panel.textContent).toContain('registramos o seu endereço IP e a sua localização aproximada')
    expect(panel.textContent).toContain('dono da barbearia recebe o seu nome, celular e localização')
    expect(panel.querySelector('.privacy')).not.toBeNull()
  })

  it('envia os dados do cadastro e mostra a instrução de confirmar o e-mail', async () => {
    api.mockImplementation(async (path) => (path === '/auth/config' ? { google_client_id: null } : { detail: 'ok' }))
    await mountLogin()
    const panel = await fillSignup()
    submitBtn(panel).click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/auth/register', { method: 'POST', body: {
      name: 'Maria Souza', phone: '(11) 98888-7777', email: 'maria@gmail.com',
      password: 'uma-senha-forte-1', password_confirm: 'uma-senha-forte-1' } })
    expect(bodyText()).toContain('Enviamos um e-mail para maria@gmail.com')
    expect(bodyText()).toContain('o dono da barbearia precisa liberar')
  })

  it('erro do cadastro (ex.: muitas tentativas) aparece e o formulário continua', async () => {
    api.mockImplementation(async (path) => {
      if (path === '/auth/config') return { google_client_id: null }
      throw Object.assign(new Error('Muitas tentativas. Tente novamente mais tarde.'), { status: 429 })
    })
    await mountLogin()
    const panel = await fillSignup()
    submitBtn(panel).click(); await flushPromises()
    expect(bodyText()).toContain('Muitas tentativas')
    expect(submitBtn(panel)).toBeTruthy()
  })

  it('e-mail não confirmado (403) oferece reenviar a confirmação', async () => {
    api.mockImplementation(async (path) => {
      if (path === '/auth/config') return { google_client_id: null }
      if (path === '/auth/resend-verification') return { detail: 'Enviamos um novo e-mail.' }
      throw Object.assign(new Error('Confirme seu e-mail antes de entrar.'), { status: 403 })
    })
    await mountLogin()
    await typeInto(document.querySelector('input[type="email"]'), 'maria@gmail.com')
    await typeInto(document.querySelector('input[type="password"]'), 'uma-senha-forte-1')
    document.querySelector('form button[type="submit"]').click(); await flushPromises()
    expect(bodyText()).toContain('Confirme seu e-mail antes de entrar')
    const resend = [...document.querySelectorAll('a')].find((a) => a.textContent.includes('Reenviar e-mail de confirmação'))
    resend.click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/auth/resend-verification', { method: 'POST', body: { email: 'maria@gmail.com' } })
    expect(setToken).not.toHaveBeenCalled()
  })
})
