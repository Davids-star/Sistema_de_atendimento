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
  date_from: '2029-03-01', date_to: '2029-03-31', total_appointments: 8,
  by_status: { pending: 1, confirmed: 1, cancelled: 1, completed: 4, no_show: 1 },
  revenue_cents: 15500, expected_revenue_cents: 6000, no_show_rate: 0.2, unique_clients: 2, new_clients: 2,
  top_services: [{ service_id: 1, name: 'Corte', count: 3, revenue_cents: 12500 }],
}
const DAYS = Array.from({ length: 31 }, (_, i) => ({
  date: `2029-03-${String(i + 1).padStart(2, '0')}`, total: i === 4 ? 2 : 0, by_status: {},
}))
const REVENUE = { group_by: 'day', total_cents: 15500, points: [{ period: '2029-03-05', revenue_cents: 7000, completed_count: 2 }] }

function respond({ stale = [] } = {}) {
  api.mockImplementation(async (path) => {
    if (path === '/dashboard/summary') return SUMMARY
    if (path === '/dashboard/appointments-by-day') return DAYS
    if (path === '/dashboard/revenue') return REVENUE
    if (path === '/appointments') return stale
    throw new Error(`rota inesperada ${path}`)
  })
}
const render = async () => {
  const vuetify = createVuetify({ components, directives })
  const w = mount({ template: '<v-app><DashboardView /></v-app>', components: { DashboardView } },
                  { global: { plugins: [vuetify] }, attachTo: document.body })
  await flushPromises()
  return w
}

beforeEach(() => { api.mockReset(); document.body.innerHTML = '' })

describe('DashboardView', () => {
  it('mostra os indicadores formatados', async () => {
    respond()
    const text = norm((await render()).text())
    expect(text).toContain('R$ 155,00')      // faturamento registrado
    expect(text).toContain('R$ 60,00')       // previsto
    expect(text).toContain('20%')            // taxa de ausência
    expect(text).toContain('Corte')
    expect(text).toContain('R$ 125,00')      // faturamento do serviço
  })

  it('pede os dados do mês atual à API', async () => {
    respond()
    await render()
    const calls = api.mock.calls.filter(([p]) => p.startsWith('/dashboard'))
    expect(calls.map(([p]) => p).sort()).toEqual(['/dashboard/appointments-by-day', '/dashboard/revenue', '/dashboard/summary'])
    for (const [, opts] of calls) expect(opts.params.date_from).toMatch(/^\d{4}-\d{2}-01$/)
  })

  it('desenha uma barra por dia e destaca o dia com agendamentos', async () => {
    respond()
    const w = await render()
    expect(w.findAll('.chart')[0].findAll('.col')).toHaveLength(31)
    expect(w.find('[title="05/03: 2 agendamento(s)"]').exists()).toBe(true)
  })

  it('avisa quando há agendamentos sem desfecho', async () => {
    respond({ stale: [{ id: 1 }, { id: 2 }, { id: 3 }] })
    expect(norm((await render()).text())).toContain('3 agendamento(s) já terminaram')
  })

  it('não mostra o aviso quando está tudo em dia', async () => {
    respond()
    expect(norm((await render()).text())).not.toContain('já terminaram')
  })

  it('mostra o erro da API', async () => {
    api.mockRejectedValue(Object.assign(new Error('Sem conexão com o servidor.'), { status: 0 }))
    expect(norm((await render()).text())).toContain('Sem conexão com o servidor.')
  })

  describe('hoje, tabela dia a dia e valor no gráfico', () => {
    const rows = (w) => [...w.findAll('.daily tbody tr')].map((tr) => norm(tr.text()))

    it('o atalho Hoje pede só o dia de hoje', async () => {
      respond()
      const w = await render()
      api.mockClear(); respond()
      const hoje = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Hoje')
      hoje.click(); await flushPromises()
      const p = api.mock.calls.find(([path]) => path === '/dashboard/summary')[1].params
      expect(p.date_from).toBe(p.date_to)
      expect(p.date_from).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('mostra a tabela dia a dia só com os dias que tiveram movimento, com o faturamento de cada um', async () => {
      respond()
      const w = await render()
      expect(norm(w.text())).toContain('Dia a dia')
      expect(rows(w)).toHaveLength(1)                                       // só o dia 05 teve movimento
      expect(rows(w)[0]).toContain('05/03/2029'); expect(rows(w)[0]).toContain('2')        // 2 agendamentos
      expect(rows(w)[0]).toContain('R$ 70,00')                                              // faturamento do dia
      expect(norm(w.find('.daily tfoot').text())).toContain('R$ 70,00')                    // total
    })

    it('o interruptor mostra também os dias sem movimento', async () => {
      respond()
      const w = await render()
      expect(rows(w)).toHaveLength(1)
      await w.find('.daily').element.closest('.v-card').querySelector('input[type="checkbox"]').click()
      await flushPromises()
      expect(rows(w)).toHaveLength(31)
    })

    it('explica que só atendimentos concluídos entram no faturamento', async () => {
      respond()
      expect(norm((await render()).text())).toContain('Concluído')
    })

    it('tocar numa barra escreve o valor do dia acima do gráfico', async () => {
      respond()
      const w = await render()
      const chart = w.findAll('.chart')[1]                                   // gráfico de faturamento
      expect(norm(w.text())).toContain('Toque ou passe o mouse')
      await chart.findAll('.col')[4].trigger('click')                        // 05/03
      expect(norm(w.text())).toContain('05/03: R$ 70,00')
    })

    it('em período longo a tabela vira "Mês a mês"', async () => {
      api.mockImplementation(async (path) => {
        if (path === '/dashboard/summary') return SUMMARY
        if (path === '/dashboard/appointments-by-day') return []
        if (path === '/dashboard/revenue') return { group_by: 'month', total_cents: 20000, points: [
          { period: '2029-01', revenue_cents: 8000, completed_count: 2 }, { period: '2029-02', revenue_cents: 12000, completed_count: 3 }] }
        return []
      })
      const w = await render()
      expect(norm(w.text())).toContain('Mês a mês')
      expect(rows(w)).toEqual(expect.arrayContaining([expect.stringContaining('01/2029'), expect.stringContaining('R$ 120,00')]))
      expect(norm(w.find('.daily tfoot').text())).toContain('R$ 200,00')
    })
  })
})
