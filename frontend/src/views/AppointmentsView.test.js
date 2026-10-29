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

describe('AppointmentsView: ver o que está marcado', () => {
  const tomorrow = (h) => new Date(Date.now() + 86400000 + h * 3600000).toISOString()
  const dayAfter = (h) => new Date(Date.now() + 2 * 86400000 + h * 3600000).toISOString()
  const onlyUpcoming = (list) => api.mockImplementation(async (path, opts = {}) => {
    if (path === '/dashboard/appointments-by-day') return []
    if (path === '/appointments' && opts.params?.upcoming) return list.slice(0, opts.params.limit ?? 999)
    if (path === '/appointments' && !opts.method) return []                    // o dia de hoje está vazio
    return []
  })

  it('dia vazio: avisa qual é o próximo agendamento e leva até ele', async () => {
    onlyUpcoming([appt({ id: 7, starts_at: tomorrow(1), ends_at: tomorrow(2), status: 'confirmed', client_name: 'Felipe', service_name: 'Unha em gel' })])
    await mountView(AppointmentsView)
    const t = bodyText()
    expect(t).toContain('Nenhum agendamento neste dia')
    expect(t).toContain('Seu próximo agendamento é')
    expect(t).toContain('Felipe · Unha em gel')
    await clickButton('Ver esse dia')
    const lastDayCall = api.mock.calls.filter(([p, o]) => p === '/appointments' && o.params?.date_from).at(-1)[1].params
    expect(lastDayCall.date_from).toBe(lastDayCall.date_to)                      // foi para um dia só
    expect(lastDayCall.date_from).not.toBe(new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo' }).format(new Date()))
  })

  it('dia vazio e nada marcado no futuro: não mostra o aviso do próximo', async () => {
    onlyUpcoming([])
    await mountView(AppointmentsView)
    expect(bodyText()).toContain('Nenhum agendamento neste dia')
    expect(bodyText()).not.toContain('Seu próximo agendamento')
  })

  it('dia com agendamentos não faz a consulta extra do próximo', async () => {
    backend([appt()])
    await mountView(AppointmentsView)
    expect(api.mock.calls.some(([, o]) => o?.params?.upcoming)).toBe(false)
    expect(bodyText()).not.toContain('Seu próximo agendamento')
  })

  it('aba "Próximos" lista tudo daqui para frente, agrupado por dia', async () => {
    onlyUpcoming([
      appt({ id: 1, starts_at: tomorrow(1), ends_at: tomorrow(2), status: 'confirmed', client_name: 'Ana' }),
      appt({ id: 2, starts_at: tomorrow(3), ends_at: tomorrow(4), status: 'pending', client_name: 'Bia' }),
      appt({ id: 3, starts_at: dayAfter(1), ends_at: dayAfter(2), status: 'confirmed', client_name: 'Carla' }),
    ])
    await mountView(AppointmentsView)
    await clickButton('Próximos')
    expect(api.mock.calls.some(([p, o]) => p === '/appointments' && o.params?.upcoming === true && o.params?.limit === 200)).toBe(true)
    const t = bodyText()
    expect(t).toContain('Ana'); expect(t).toContain('Bia'); expect(t).toContain('Carla')
    expect(t).toContain('Daqui para frente')
    expect(document.querySelectorAll('.day-head')).toHaveLength(2)              // 2 dias diferentes = 2 títulos (Ana e Bia no mesmo dia)
    expect(document.querySelectorAll('.appt')).toHaveLength(3)
  })

  it('aba "Próximos" vazia explica que não há nada marcado', async () => {
    onlyUpcoming([])
    await mountView(AppointmentsView)
    await clickButton('Próximos')
    expect(bodyText()).toContain('Nenhum agendamento marcado daqui para frente')
  })

  it('na aba "Próximos" dá para criar um agendamento e as ações continuam disponíveis', async () => {
    onlyUpcoming([appt({ id: 1, starts_at: tomorrow(1), ends_at: tomorrow(2), status: 'pending' })])
    await mountView(AppointmentsView)
    await clickButton('Próximos')
    expect(buttonTexts().some((b) => b.includes('Confirmar'))).toBe(true)
    expect(buttonTexts().some((b) => b.includes('Novo agendamento'))).toBe(true)
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
