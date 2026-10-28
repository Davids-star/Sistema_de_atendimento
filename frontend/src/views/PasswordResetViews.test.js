import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

vi.mock('../api', () => ({ api: vi.fn(), setToken: vi.fn() }))
import { api } from '../api'
import { bodyText, mountView, typeInto } from '../test-helpers'
import ForgotPasswordView from './ForgotPasswordView.vue'
import ResetPasswordView from './ResetPasswordView.vue'

const makeRouter = () => createRouter({ history: createMemoryHistory(), routes: [
  { path: '/login', name: 'login', component: { template: '<i/>' } },
  { path: '/esqueci-senha', name: 'forgot', component: { template: '<i/>' } },
  { path: '/redefinir-senha', name: 'reset', component: ResetPasswordView },
] })
const button = (text) => [...document.querySelectorAll('button, a')].find((b) => b.textContent.trim().includes(text))
beforeEach(() => { api.mockReset(); document.body.innerHTML = '' })

describe('ForgotPasswordView', () => {
  it('envia o e-mail e mostra a mensagem neutra', async () => {
    api.mockResolvedValue({ detail: 'ok' })
    await mountView(ForgotPasswordView, {}, [makeRouter()])
    expect(button('Enviar link').disabled).toBe(true)
    await typeInto(document.querySelector('input[type="email"]'), 'dono@x.com')
    button('Enviar link').click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/auth/forgot-password', { method: 'POST', body: { email: 'dono@x.com' } })
    expect(bodyText()).toContain('Se o e-mail estiver cadastrado')
  })

  it('mostra o erro de excesso de tentativas', async () => {
    api.mockRejectedValue(Object.assign(new Error('Muitas tentativas. Tente novamente mais tarde.'), { status: 429 }))
    await mountView(ForgotPasswordView, {}, [makeRouter()])
    await typeInto(document.querySelector('input[type="email"]'), 'dono@x.com')
    button('Enviar link').click(); await flushPromises()
    expect(bodyText()).toContain('Muitas tentativas')
    expect(bodyText()).not.toContain('enviamos as instruções')
  })
})

describe('ResetPasswordView', () => {
  const open = async (query = '?token=' + 'a'.repeat(43)) => {
    const r = makeRouter(); await r.push('/redefinir-senha' + query)
    await mountView(ResetPasswordView, {}, [r])
  }
  const fill = async (a, b) => {
    const [p1, p2] = document.querySelectorAll('input[type="password"]')
    await typeInto(p1, a); await typeInto(p2, b)
  }

  it('sem token na URL, mostra link inválido', async () => {
    await open('')
    expect(bodyText()).toContain('inválido ou expirou')
    expect(bodyText()).toContain('Pedir um novo link')
  })

  it('só habilita com senha forte e confirmação igual', async () => {
    await open()
    await fill('curta', 'curta')
    expect(button('Salvar nova senha').disabled).toBe(true)
    await fill('uma-senha-forte-1', 'diferente-123456')
    expect(button('Salvar nova senha').disabled).toBe(true)
    await fill('uma-senha-forte-1', 'uma-senha-forte-1')
    expect(button('Salvar nova senha').disabled).toBe(false)
  })

  it('envia o token da URL com a nova senha e confirma o sucesso', async () => {
    api.mockResolvedValue(null)
    await open()
    await fill('uma-senha-forte-1', 'uma-senha-forte-1')
    button('Salvar nova senha').click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/auth/reset-password', { method: 'POST', body: { token: 'a'.repeat(43), new_password: 'uma-senha-forte-1' } })
    expect(bodyText()).toContain('Senha alterada com sucesso')
  })

  it('link expirado ou já usado (400) leva a pedir outro', async () => {
    api.mockRejectedValue(Object.assign(new Error('Link inválido ou expirado. Peça um novo.'), { status: 400 }))
    await open()
    await fill('uma-senha-forte-1', 'uma-senha-forte-1')
    button('Salvar nova senha').click(); await flushPromises()
    expect(bodyText()).toContain('inválido ou expirou')
    expect(bodyText()).toContain('Pedir um novo link')
  })

  it('outros erros (ex.: bloqueio) aparecem sem descartar o formulário', async () => {
    api.mockRejectedValue(Object.assign(new Error('Muitas tentativas.'), { status: 429 }))
    await open()
    await fill('uma-senha-forte-1', 'uma-senha-forte-1')
    button('Salvar nova senha').click(); await flushPromises()
    expect(bodyText()).toContain('Muitas tentativas.')
    expect(button('Salvar nova senha')).toBeTruthy()
  })
})
