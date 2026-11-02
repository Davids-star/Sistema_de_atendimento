import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

vi.mock('../api', () => ({ api: vi.fn() }))
import { api } from '../api'
import DashboardView from './DashboardView.vue'

const norm = (s) => s.replace(/ /g, ' ').replace(/\s+/g, ' ')
const SUMMARY = {
  date_from: '2029-03-01', date_to: '2029-03-31', total_appointments: 8, scheduled_appointments: 7,
  by_status: { pending: 1, confirmed: 1, cancelled: 1, completed: 4, no_show: 1 },
  revenue_cents: 15500, expected_revenue_cents: 6000, no_show_rate: 0.2, unique_clients: 2, new_clients: 2,
  top_services: [{ service_id: 1, name: 'Corte', count: 3, revenue_cents: 12500 }],
}
const DAYS = Array.from({ length: 31 }, (_, i) => ({
  date: `2029-03-${String(i + 1).padStart(2, '0')}`, total: i === 4 ? 2 : 0, by_status: {},
}))
const REVENUE = { group_by: 'day', total_cents: 15500, points: [{ period: '2029-03-05', revenue_cents: 7000, completed_count: 2 }] }

function respond() {
  api.mockImplementation(async (path) => {
    if (path === '/dashboard/summary') return SUMMARY
    if (path === '/dashboard/appointments-by-day') return DAYS
    if (path === '/dashboard/revenue') return REVENUE
    throw new Error(`rota inesperada ${path}`)
  })
}

const render = async () => {
  const vuetify = createVuetify({ components, directives })
  const w = mount(
    { template: '<v-app><DashboardView /></v-app>', components: { DashboardView } },
    {
      global: {
        plugins: [vuetify],
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
        },
      },
      attachTo: document.body,
    }
  )
  await flushPromises()
  return w
}

beforeEach(() => { api.mockReset(); document.body.innerHTML = '' })

describe('DashboardView', () => {
  it('mostra os indicadores devolvidos pela API formatados', async () => {
    respond()
    const text = norm((await render()).text())
    expect(text).toContain('Faturamento Registrado')
    expect(text).toContain('R$ 155,00')
    expect(text).toContain('Serviços Mais Realizados')
    expect(text).toContain('Corte')
    expect(text).toContain('3 vezes')
    expect(text).toContain('R$ 125,00')
    expect(text).toContain('Agendamentos')
    expect(text).toContain('7')
    expect(text).toContain('Concluídos: 4')
    expect(text).toContain('Faturamento Previsto')
    expect(text).toContain('R$ 60,00')
    expect(text).toContain('Pendentes e Confirmados')
    expect(text).toContain('Agendamentos por dia')
    expect(text).toContain('20%')
  })

  it('pede os dados do período à API', async () => {
    respond()
    await render()
    const dash = api.mock.calls.filter(([p]) => p.startsWith('/dashboard'))
    expect(new Set(dash.map(([p]) => p))).toEqual(new Set(['/dashboard/appointments-by-day', '/dashboard/revenue', '/dashboard/summary']))
  })

  it('mostra a visão diária alimentada pelos dados da API', async () => {
    respond()
    const w = await render()
    expect(w.text()).toContain('Dia com mais agendamentos')
    expect(w.findAll('.breakdown tbody tr')).toHaveLength(31)
  })

  it('muda de período através do dropdown', async () => {
    respond()
    const w = await render()
    api.mockClear()
    respond()
    const select = w.find('.period-dropdown')
    await select.setValue('today')
    await flushPromises()
    const p = api.mock.calls.find(([path]) => path === '/dashboard/summary')[1].params
    expect(p.date_from).toBe(p.date_to)
  })

  it('mostra o erro da API quando a requisição falha', async () => {
    api.mockRejectedValue(new Error('Sem conexão com o servidor.'))
    expect(norm((await render()).text())).toContain('Sem conexão com o servidor.')
  })

  it('não inventa barras ou contagens quando a API retorna um período vazio', async () => {
    api.mockImplementation(async (path) => {
      if (path === '/dashboard/summary') return {
        scheduled_appointments: 0, total_appointments: 0, by_status: { completed: 0 },
        revenue_cents: 0, expected_revenue_cents: 0, no_show_rate: null, top_services: [],
      }
      if (path === '/dashboard/revenue') return { points: [] }
      if (path === '/dashboard/appointments-by-day') return []
      throw new Error(`rota inesperada ${path}`)
    })
    const w = await render()
    const text = norm(w.text())
    expect(text).toContain('R$ 0,00')
    expect(text).toContain('Nenhum serviço concluído neste período.')
    expect(w.findAll('.spark-bar')).toHaveLength(0)
    expect(text).not.toContain('0%')
  })
})
