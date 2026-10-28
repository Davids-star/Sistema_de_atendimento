import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({ api: vi.fn() }))
import { api } from '../api'
import AppointmentDialog from '../components/AppointmentDialog.vue'
import { bodyText, buttonTexts, clickButton, mountView } from '../test-helpers'
import AppointmentsView from './AppointmentsView.vue'

const appt = (over) => ({
  id: 1, client_id: 5, client_name: 'Ana Souza', client_phone: '5511999998888', service_id: 3, service_name: 'Corte',
  starts_at: '2099-03-05T12:00:00Z', ends_at: '2099-03-05T12:30:00Z', status: 'pending', price_cents: 4000,
  source: 'admin', notes: null, created_at: '2099-01-01T00:00:00Z', ...over,
})
const calls = (method, pathPart) => api.mock.calls.filter(([p, o]) => (o?.method ?? 'GET') === method && p.includes(pathPart))

function backend(list) {
  api.mockImplementation(async (path, opts = {}) => {
    if (path === '/appointments' && !opts.method) return list
    if (path === '/dashboard/appointments-by-day') return []
    if (opts.method === 'POST' || opts.method === 'PATCH') return { ...list[0], warnings: [] }
    if (path === '/services') return [{ id: 3, name: 'Corte', duration_minutes: 30, price_cents: 4000 }]
    if (path === '/availability') return { slots: ['2099-03-05T13:00:00Z', '2099-03-05T13:30:00Z'] }
    return []
  })
}
beforeEach(() => { api.mockReset(); document.body.innerHTML = '' })

describe('AppointmentsView', () => {
  it('lista com nome, serviço, preço, horário local e status', async () => {
    backend([appt()])
    await mountView(AppointmentsView)
    const t = bodyText()
    expect(t).toContain('Ana Souza')
    expect(t).toContain('(11) 99999-8888')
    expect(t).toContain('Corte · R$ 40,00')
    expect(t).toContain('09:00')           // 12:00Z = 09:00 em São Paulo
    expect(t).toContain('Pendente')
  })

  it('mostra só as ações que cabem em cada status', async () => {
    backend([appt({ id: 1, status: 'pending' }), appt({ id: 2, status: 'confirmed' }), appt({ id: 3, status: 'cancelled' })])
    await mountView(AppointmentsView)
    const b = buttonTexts()
    expect(b.filter((x) => x.includes('Confirmar'))).toHaveLength(1)   // só o pendente
    expect(b.filter((x) => x.includes('Cancelar'))).toHaveLength(2)    // pendente e confirmado
    expect(b.some((x) => x.includes('Concluir'))).toBe(false)          // futuro: ainda não começou
  })

  it('oferece Concluir / Não veio quando o horário já começou', async () => {
    backend([appt({ status: 'confirmed', starts_at: '2020-03-05T12:00:00Z', ends_at: '2020-03-05T12:30:00Z' })])
    await mountView(AppointmentsView)
    expect(buttonTexts().some((x) => x.includes('Concluir'))).toBe(true)
    expect(buttonTexts().some((x) => x.includes('Não veio'))).toBe(true)
  })

  it('confirmar executa direto', async () => {
    backend([appt()])
    await mountView(AppointmentsView)
    await clickButton('Confirmar')
    expect(calls('POST', '/appointments/1/confirm')).toHaveLength(1)
  })

  it('cancelar pede confirmação e só então chama a API', async () => {
    backend([appt()])
    await mountView(AppointmentsView)
    await clickButton('Cancelar')
    expect(calls('POST', '/cancel')).toHaveLength(0)
    expect(bodyText()).toContain('O horário voltará a ficar disponível')
    await clickButton('Voltar')
    expect(calls('POST', '/cancel')).toHaveLength(0)
    await clickButton('Cancelar'); await flushPromises()
    const dialogButtons = [...document.body.querySelectorAll('.v-overlay--active button')]
    dialogButtons.find((b) => b.textContent.trim() === 'Cancelar').click()
    await flushPromises()
    expect(calls('POST', '/appointments/1/cancel')).toHaveLength(1)
  })

  it('dia vazio mostra mensagem', async () => {
    backend([])
    await mountView(AppointmentsView)
    expect(bodyText()).toContain('Nenhum agendamento neste dia')
  })

  it('"Sem desfecho" consulta needs_outcome', async () => {
    backend([])
    await mountView(AppointmentsView)
    await clickButton('Sem desfecho')
    expect(api.mock.calls.some(([p, o]) => p === '/appointments' && o.params.needs_outcome === true)).toBe(true)
    expect(bodyText()).toContain('Tudo em dia')
  })

  it('erro da API vira aviso e não quebra a tela', async () => {
    api.mockRejectedValue(new Error('Sem conexão com o servidor.'))
    await mountView(AppointmentsView)
    expect(bodyText()).toContain('Nenhum agendamento')
  })
})

describe('AppointmentDialog (remarcar)', () => {
  it('mostra horários livres e envia só o horário alterado', async () => {
    backend([appt()])
    await mountView(AppointmentDialog, { modelValue: true, appointment: appt(), initialDay: '2099-03-05' })
    const t = bodyText()
    expect(t).toContain('Editar agendamento')
    expect(t).toContain('Ana Souza')
    expect(t).toContain('09:00 (atual)')
    expect(t).toContain('10:00'); expect(t).toContain('10:30')       // 13:00Z e 13:30Z
    expect(calls('GET', '/availability')[0][1].params).toEqual({ date: '2099-03-05', service_id: 3 })

    await clickButton('10:30')
    await clickButton('Salvar alterações')
    const [path, opts] = calls('PATCH', '/appointments/1')[0]
    expect(path).toBe('/appointments/1')
    expect(opts.body).toEqual({ starts_at: '2099-03-05T13:30:00Z' })
  })

  it('sem mudanças, não chama a API', async () => {
    backend([appt()])
    await mountView(AppointmentDialog, { modelValue: true, appointment: appt(), initialDay: '2099-03-05' })
    await clickButton('Salvar alterações')
    expect(calls('PATCH', '/appointments')).toHaveLength(0)
  })

  it('conflito (409) mostra o erro e mantém o diálogo aberto', async () => {
    backend([appt()])
    const base = api.getMockImplementation()
    api.mockImplementation(async (p, o = {}) => { if (o.method === 'PATCH') throw Object.assign(new Error('Esse horário já está ocupado'), { status: 409 }); return base(p, o) })
    await mountView(AppointmentDialog, { modelValue: true, appointment: appt(), initialDay: '2099-03-05' })
    await clickButton('10:00'); await clickButton('Salvar alterações')
    expect(bodyText()).toContain('Editar agendamento')
  })
})

describe('AppointmentDialog (novo)', () => {
  it('Agendar fica desabilitado até preencher tudo', async () => {
    backend([])
    await mountView(AppointmentDialog, { modelValue: true, appointment: null, initialDay: '2099-03-05' })
    const btn = [...document.body.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Agendar')
    expect(btn.disabled).toBe(true)
    expect(bodyText()).toContain('Novo agendamento')
    expect(bodyText()).toContain('Escolha o serviço para ver os horários livres')
  })
})
