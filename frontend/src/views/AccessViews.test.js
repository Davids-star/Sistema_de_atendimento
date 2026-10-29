import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

vi.mock('../api', () => ({ api: vi.fn(), setToken: vi.fn() }))
import { api, setToken } from '../api'
import { resetSession, session } from '../session'
import { bodyText, clickButton, mountView, typeInto } from '../test-helpers'
import CompleteProfileView from './CompleteProfileView.vue'
import ConfirmEmailView from './ConfirmEmailView.vue'
import PendingApprovalView from './PendingApprovalView.vue'
import UsersView from './UsersView.vue'

const makeRouter = () => createRouter({ history: createMemoryHistory(), routes: [
  { path: '/login', name: 'login', component: { template: '<i/>' } },
  { path: '/', name: 'dashboard', component: { template: '<i/>' } },
  { path: '/aguardando-liberacao', name: 'pending', component: { template: '<i/>' } },
  { path: '/confirmar-email', name: 'confirm-email', component: ConfirmEmailView },
] })
const calls = (method, part) => api.mock.calls.filter(([p, o]) => (o?.method ?? 'GET') === method && p.includes(part))
beforeEach(() => { api.mockReset(); setToken.mockReset(); resetSession(); document.body.innerHTML = '' })

const U = (over) => ({ id: 1, name: 'Fulano Silva', email: 'f@gmail.com', phone: '5511988887777', status: 'pending_approval',
  is_owner: false, email_verified_at: '2029-01-01T10:00:00Z', approved_at: null, created_at: '2029-01-01T10:00:00Z', ...over })

describe('UsersView (o dono libera o acesso)', () => {
  const users = [
    U({ id: 2, name: 'Ana Pendente', email: 'ana@gmail.com' }),
    U({ id: 3, name: 'Beto Ativo', email: 'beto@gmail.com', status: 'active', approved_at: '2029-01-02T10:00:00Z' }),
    U({ id: 4, name: 'Carla Dona', email: 'carla@gmail.com', status: 'active', is_owner: true }),
    U({ id: 5, name: 'Davi Sem Confirmar', email: 'davi@gmail.com', status: 'pending_email', phone: null }),
    U({ id: 6, name: 'Eva Off', email: 'eva@gmail.com', status: 'disabled' }),
  ]
  const open = async () => {
    api.mockImplementation(async (path, o = {}) => (o.method === 'POST' ? U({ status: 'active' }) : users))
    session.user = { id: 4, is_owner: true }
    await mountView(UsersView)
  }
  const chip = (text) => [...document.querySelectorAll('.v-chip')].find((c) => c.textContent.includes(text))

  it('abre em "Aguardando liberação" e mostra quem está esperando, com a contagem de cada grupo', async () => {
    await open()
    const t = bodyText()
    expect(t).toContain('Ana Pendente'); expect(t).toContain('(11) 98888-7777')
    expect(t).not.toContain('Beto Ativo')
    expect(chip('Aguardando liberação').textContent).toContain('1')
    expect(chip('Com acesso').textContent).toContain('2')
  })

  it('liberar acesso chama a API e recarrega a lista', async () => {
    await open()
    await clickButton('Liberar acesso')
    expect(calls('POST', '/users/2/approve')).toHaveLength(1)
    expect(calls('GET', '/users').length).toBeGreaterThan(1)
  })

  it('o dono não tem botão de desativar; os demais ativos têm, com confirmação', async () => {
    await open()
    await clickButton('Com acesso')
    const buttons = [...document.querySelectorAll('button')].filter((b) => b.textContent.includes('Desativar'))
    expect(buttons).toHaveLength(1)                                   // só o Beto (a Carla é a dona/você)
    expect(bodyText()).toContain('Dono')
    buttons[0].click(); await flushPromises()
    expect(bodyText()).toContain('perde o acesso imediatamente')
    expect(calls('POST', '/deactivate')).toHaveLength(0)              // ainda não executou
    const confirm = [...document.querySelectorAll('.v-overlay--active button')].find((b) => b.textContent.trim() === 'Desativar')
    confirm.click(); await flushPromises()
    expect(calls('POST', '/users/3/deactivate')).toHaveLength(1)
  })

  it('desativados podem ser reativados; quem não confirmou o e-mail não pode ser liberado', async () => {
    await open()
    await clickButton('E-mail não confirmado')
    expect(bodyText()).toContain('Davi Sem Confirmar'); expect(bodyText()).toContain('Celular ainda não informado')
    expect([...document.querySelectorAll('button')].some((b) => b.textContent.includes('Liberar acesso'))).toBe(false)
    await clickButton('Desativados')
    await clickButton('Reativar')
    expect(calls('POST', '/users/6/reactivate')).toHaveLength(1)
  })
})

describe('CompleteProfileView (celular)', () => {
  it('só continua com um celular válido e grava no perfil', async () => {
    api.mockResolvedValue({ id: 1, name: 'Ana Souza', phone: '5511977776666', approved: false })
    session.user = { name: 'Ana Souza' }
    const r = makeRouter(); await r.push('/login')
    await mountView(CompleteProfileView, {}, [r])
    expect(bodyText()).toContain('Quase lá, Ana')
    const btn = () => [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Continuar'))
    expect(btn().disabled).toBe(true)
    await typeInto(document.querySelector('input'), '123')
    expect(btn().disabled).toBe(true)
    await typeInto(document.querySelector('input'), '(11) 97777-6666')
    expect(btn().disabled).toBe(false)
    btn().click(); await flushPromises()
    expect(api).toHaveBeenCalledWith('/auth/me', { method: 'PATCH', body: { phone: '(11) 97777-6666' } })
    expect(session.user.phone).toBe('5511977776666')
    expect(r.currentRoute.value.name).toBe('dashboard')
  })
})

describe('PendingApprovalView', () => {
  it('explica a espera e, se já foi liberado, entra no painel', async () => {
    session.user = { name: 'Ana Souza', approved: false }
    session.loaded = true
    api.mockResolvedValue({ name: 'Ana Souza', approved: true, phone: '5511977776666' })
    const r = makeRouter(); await r.push('/aguardando-liberacao')
    await mountView(PendingApprovalView, {}, [r])
    expect(bodyText()).toContain('Sua conta foi criada, Ana')
    expect(bodyText()).toContain('liberado pelo dono')
    await clickButton('Verificar novamente')
    expect(r.currentRoute.value.name).toBe('dashboard')
  })

  it('ainda não liberado: avisa e continua esperando', async () => {
    session.user = { name: 'Ana Souza', approved: false }; session.loaded = true
    api.mockResolvedValue({ name: 'Ana Souza', approved: false, phone: '5511977776666' })
    const r = makeRouter(); await r.push('/aguardando-liberacao')
    await mountView(PendingApprovalView, {}, [r])
    await clickButton('Verificar novamente')
    expect(bodyText()).toContain('Ainda não foi liberado')
    expect(r.currentRoute.value.name).toBe('pending')
  })
})

describe('ConfirmEmailView', () => {
  const open = async (query) => { const r = makeRouter(); await r.push('/confirmar-email' + query); await mountView(ConfirmEmailView, {}, [r]) }

  it('confirma o e-mail usando o token da URL', async () => {
    api.mockResolvedValue(null)
    await open('?token=' + 'a'.repeat(43))
    expect(api).toHaveBeenCalledWith('/auth/verify-email', { method: 'POST', body: { token: 'a'.repeat(43) } })
    expect(bodyText()).toContain('E-mail confirmado!')
  })
  it('link inválido ou expirado', async () => {
    api.mockRejectedValue(Object.assign(new Error('Link inválido'), { status: 400 }))
    await open('?token=' + 'a'.repeat(43))
    expect(bodyText()).toContain('inválido ou expirou')
  })
  it('sem token na URL nem chama a API', async () => {
    await open('')
    expect(api).not.toHaveBeenCalled()
    expect(bodyText()).toContain('inválido ou expirou')
  })
})
