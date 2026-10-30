import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({ api: vi.fn() }))
import { api } from '../api'
import { inbox, resetInbox } from '../notifications'
import { bodyText, clickButton, mountView, norm } from '../test-helpers'
import HandoffView from './HandoffView.vue'

const conv = (over = {}) => ({ id: 1, channel: 'telegram', client_name: 'Maria Souza', client_phone: '5511977776666', phone_verified: true, needs_human: true,
  handoff_at: new Date(Date.now() - 12 * 60000).toISOString(), handoff_note: 'preciso remarcar', last_message_at: null, ...over })
const serve = (list) => api.mockImplementation(async (path, opts = {}) => {
  if (path === '/conversations' && !opts.method) return list
  return {}
})
const calls = (method, part) => api.mock.calls.filter(([p, o]) => (o?.method ?? 'GET') === method && p.includes(part))
beforeEach(() => { api.mockReset(); resetInbox(); document.body.innerHTML = '' })

describe('HandoffView (Atendimento)', () => {
  it('lista quem pediu: nome, celular, canal, o que escreveu e há quanto tempo espera', async () => {
    serve([conv()])
    await mountView(HandoffView)
    const t = bodyText()
    expect(t).toContain('Maria Souza'); expect(t).toContain('(11) 97777-6666'); expect(t).toContain('Telegram')
    expect(t).toContain('“preciso remarcar”'); expect(t).toContain('esperando 12 min')
  })

  it('o botão abre o WhatsApp da cliente com a mensagem pronta, em outra aba e com segurança', async () => {
    serve([conv()])
    await mountView(HandoffView)
    const a = document.querySelector('a[href^="https://wa.me/"]')
    expect(a.getAttribute('href').startsWith('https://wa.me/5511977776666?text=')).toBe(true)
    expect(decodeURIComponent(a.getAttribute('href').split('text=')[1])).toContain('Olá, Maria! Aqui é do Agenda. Vi que você pediu para falar com a gente')
    expect(a.getAttribute('target')).toBe('_blank'); expect(a.getAttribute('rel')).toBe('noopener noreferrer')
  })

  it('sem celular informado: explica e não oferece link', async () => {
    serve([conv({ client_name: null, client_phone: null })])
    await mountView(HandoffView)
    expect(bodyText()).toContain('Cliente ainda sem cadastro'); expect(bodyText()).toContain('Ainda não informou o celular')
    expect(document.querySelector('a[href^="https://wa.me/"]')).toBeNull()
    expect(bodyText()).toContain('Sem WhatsApp para responder')
  })

  it('"Marcar como resolvido" chama a API e tira a pessoa da lista', async () => {
    serve([conv({ id: 1 }), conv({ id: 2, client_name: 'Ana Lima', client_phone: '5511912345678' })])
    await mountView(HandoffView)
    await clickButton('Marcar como resolvido')
    expect(calls('POST', '/conversations/1/resolve')).toHaveLength(1)
    expect(bodyText()).not.toContain('Maria Souza'); expect(bodyText()).toContain('Ana Lima')
  })

  it('se a API falhar ao resolver, a pessoa continua na lista', async () => {
    api.mockImplementation(async (path, o = {}) => { if (o.method === 'POST') throw new Error('sem rede'); return [conv()] })
    await mountView(HandoffView)
    await clickButton('Marcar como resolvido')
    expect(bodyText()).toContain('Maria Souza')
  })

  it('lista vazia mostra que está tudo em dia', async () => {
    serve([])
    await mountView(HandoffView)
    expect(bodyText()).toContain('Ninguém esperando por você')
  })

  it('"Atualizar" busca de novo', async () => {
    serve([conv()])
    await mountView(HandoffView)
    api.mockClear(); serve([conv(), conv({ id: 2, client_name: 'Bia' })])
    await clickButton('Atualizar')
    expect(bodyText()).toContain('Bia')
  })

  it('chegou um aviso novo no sino: a lista se atualiza sozinha', async () => {
    inbox.items = [{ id: 1, kind: 'appointment_cancelled', read_at: null }]
    serve([conv()])
    await mountView(HandoffView)
    serve([conv(), conv({ id: 2, client_name: 'Nova Cliente' })])
    inbox.items = [{ id: 2, kind: 'handoff', read_at: null }, ...inbox.items]; await flushPromises()
    expect(bodyText()).toContain('Nova Cliente')
  })
})
