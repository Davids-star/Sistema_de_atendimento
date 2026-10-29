import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./api', () => ({ getToken: vi.fn(), api: vi.fn() }))
vi.mock('./session', () => ({ loadUser: vi.fn() }))
import { getToken } from './api'
import { guard } from './router'
import { loadUser } from './session'

const route = (name, meta = {}, protectedRoute = true) => ({ name, meta, matched: [{ meta: protectedRoute ? { requiresAuth: true, ...meta } : meta }] })
const panel = (name = 'dashboard', meta = {}) => route(name, meta)
const user = (over = {}) => ({ phone: '5511999998888', approved: true, is_owner: false, ...over })

beforeEach(() => { getToken.mockReset(); loadUser.mockReset() })

describe('guard do roteador', () => {
  it('sem login, o painel manda para o login', async () => {
    getToken.mockReturnValue(null)
    expect(await guard(panel())).toEqual({ name: 'login' })
  })
  it('páginas públicas ficam livres (mesmo logado, sem consultar a sessão)', async () => {
    getToken.mockReturnValue('t')
    expect(await guard(route('forgot', {}, false))).toBeUndefined()
    expect(loadUser).not.toHaveBeenCalled()
  })
  it('login livre sem token', async () => {
    getToken.mockReturnValue(null)
    expect(await guard(route('login', {}, false))).toBeUndefined()
  })
  it('já logado, o login reencaminha', async () => {
    getToken.mockReturnValue('t'); loadUser.mockResolvedValue(user())
    expect(await guard(route('login', {}, false))).toEqual({ name: 'dashboard' })
  })
  it('token inválido: painel volta ao login; tela de login continua acessível', async () => {
    getToken.mockReturnValue('velho'); loadUser.mockResolvedValue(null)
    expect(await guard(panel())).toEqual({ name: 'login' })
    expect(await guard(route('login', {}, false))).toBeUndefined()
  })
  it('sem celular, tudo leva a "completar perfil" (antes mesmo da liberação)', async () => {
    getToken.mockReturnValue('t')
    loadUser.mockResolvedValue(user({ phone: null, approved: false }))
    expect(await guard(panel())).toEqual({ name: 'complete-profile' })
    expect(await guard(route('pending'))).toEqual({ name: 'complete-profile' })
    expect(await guard(route('complete-profile'))).toBeUndefined()
  })
  it('com celular mas sem liberação, fica em "aguardando"', async () => {
    getToken.mockReturnValue('t'); loadUser.mockResolvedValue(user({ approved: false }))
    expect(await guard(panel())).toEqual({ name: 'pending' })
    expect(await guard(route('pending'))).toBeUndefined()
    expect(await guard(route('complete-profile'))).toEqual({ name: 'pending' })
  })
  it('liberado entra no painel e não volta às telas de espera', async () => {
    getToken.mockReturnValue('t'); loadUser.mockResolvedValue(user())
    expect(await guard(panel())).toBeUndefined()
    expect(await guard(route('pending'))).toEqual({ name: 'dashboard' })
    expect(await guard(route('complete-profile'))).toEqual({ name: 'dashboard' })
  })
  it('tela de usuários só para o dono', async () => {
    getToken.mockReturnValue('t')
    loadUser.mockResolvedValue(user({ is_owner: false }))
    expect(await guard(panel('users', { ownerOnly: true }))).toEqual({ name: 'dashboard' })
    loadUser.mockResolvedValue(user({ is_owner: true }))
    expect(await guard(panel('users', { ownerOnly: true }))).toBeUndefined()
  })
})
