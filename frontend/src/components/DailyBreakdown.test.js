import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({ api: vi.fn() }))
import { api } from '../api'
import { mountView, norm } from '../test-helpers'
import { addDays, startOfWeek, todayISO } from '../utils/datetime'
import { viewRange } from '../utils/period'
import DailyBreakdown from './DailyBreakdown.vue'

const day = (date, total, done, noShow = 0) => ({ date, total, by_status: { pending: 0, confirmed: 0, cancelled: 0, completed: done, no_show: noShow } })

// Resposta que depende do período pedido: um item por dia, com valores previsíveis (total = dia do mês, 2 concluídos, R$ 50 cada).
function backend() {
  api.mockImplementation(async (path, { params }) => {
    const dates = []
    for (let d = params.date_from; d <= params.date_to; d = addDays(d, 1)) dates.push(d)
    if (path === '/dashboard/appointments-by-day') return dates.map((d) => day(d, Number(d.slice(8)), 2, d.endsWith('-02') ? 1 : 0))
    if (path === '/dashboard/revenue') return { group_by: 'day', points: dates.map((d) => ({ period: d, revenue_cents: 10000, completed_count: 2 })) }
  })
}
const calls = () => api.mock.calls.map(([p, o]) => ({ path: p, ...o.params }))
const lastRange = () => { const c = calls().filter((x) => x.path === '/dashboard/appointments-by-day').at(-1); return [c.date_from, c.date_to] }
const click = async (selector, text) => {
  const el = [...document.querySelectorAll(selector)].find((e) => !text || norm(e.textContent) === text)
  el.click(); await flushPromises()
}
const bodyRows = () => [...document.querySelectorAll('.breakdown tbody tr')]
beforeEach(() => { api.mockReset(); document.body.innerHTML = '' })

describe('DailyBreakdown', () => {
  it('abre na semana atual (segunda a domingo), com 7 linhas e o total', async () => {
    backend()
    const w = await mountView(DailyBreakdown)
    const { from, to } = viewRange('week', todayISO())
    expect(lastRange()).toEqual([from, to])
    expect(bodyRows()).toHaveLength(7)
    expect(norm(w.find('.breakdown tfoot').text())).toContain('R$ 700,00')                   // 7 dias x R$ 100,00
    expect(w.find('.label').text()).toContain('–')
  })

  it('cada linha da semana mostra o dia da semana, os agendamentos, os concluídos e o valor', async () => {
    backend()
    await mountView(DailyBreakdown)
    const first = norm(bodyRows()[0].textContent)
    expect(first).toMatch(/^seg \d{2}\/\d{2}/)
    expect(first).toContain('R$ 100,00')
  })

  it('"Dia" mostra só 4 números do dia (sem tabela)', async () => {
    backend()
    const w = await mountView(DailyBreakdown)
    await click('.breakdown button', 'Dia')
    expect(lastRange()).toEqual([todayISO(), todayISO()])
    expect(w.findAll('.tile')).toHaveLength(4)
    expect(document.querySelector('.breakdown table')).toBeNull()
    expect(norm(w.text())).toContain('Agendamentos')
    expect(norm(w.text())).toContain('R$ 100,00')
  })

  it('"Mês" resume o mês em poucas linhas (semanas), nunca em um dia por linha', async () => {
    backend()
    await mountView(DailyBreakdown)
    await click('.breakdown button', 'Mês')
    const { from, to } = viewRange('month', todayISO())
    expect(lastRange()).toEqual([from, to])
    expect(bodyRows().length).toBeGreaterThanOrEqual(4)
    expect(bodyRows().length).toBeLessThanOrEqual(6)
    const monthDays = (new Date(to).getTime() - new Date(from).getTime()) / 86400000 + 1
    expect(norm(document.querySelector('.breakdown tfoot').textContent)).toContain(`R$ ${(monthDays * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`)
  })

  it('as setas andam uma semana (ou um mês) e "Hoje" volta', async () => {
    backend()
    await mountView(DailyBreakdown)
    const thisWeek = viewRange('week', todayISO())
    await click('button[aria-label="Próximo"]')
    expect(lastRange()).toEqual([addDays(thisWeek.from, 7), addDays(thisWeek.to, 7)])
    await click('button[aria-label="Anterior"]'); await click('button[aria-label="Anterior"]')
    expect(lastRange()).toEqual([addDays(thisWeek.from, -7), addDays(thisWeek.to, -7)])
    await click('.breakdown button', 'Hoje')
    expect(lastRange()).toEqual([thisWeek.from, thisWeek.to])
  })

  it('"Hoje" fica desabilitado quando já está no período de hoje', async () => {
    backend()
    await mountView(DailyBreakdown)
    const hoje = [...document.querySelectorAll('.breakdown button')].find((b) => norm(b.textContent) === 'Hoje')
    expect(hoje.disabled).toBe(true)
    await click('button[aria-label="Próximo"]')
    expect([...document.querySelectorAll('.breakdown button')].find((b) => norm(b.textContent) === 'Hoje').disabled).toBe(false)
  })

  it('o tamanho do quadro é limitado (não cresce com os dados)', () => {
    const css = [...document.querySelectorAll('style')].map((s) => s.textContent).join('')
    // O componente declara altura máxima e rolagem interna: conferimos no código-fonte, já que o jsdom não calcula layout.
    const src = import.meta.glob('./DailyBreakdown.vue', { query: '?raw', import: 'default', eager: true })['./DailyBreakdown.vue']
    expect(src).toMatch(/max-height:\s*360px/)
    expect(src).toMatch(/overflow:\s*auto/)
  })

  it('ignora uma resposta antiga quando a pessoa clica rápido', async () => {
    const week = viewRange('week', todayISO())
    const slow = []                                                          // consultas da SEMANA que ficam "penduradas"
    api.mockImplementation((path, { params }) => {
      const isWeek = params.date_from === week.from && params.date_to === week.to
      const data = path === '/dashboard/revenue' ? { points: [] } : [day(params.date_from, isWeek ? 11 : 99, 0)]
      if (!isWeek) return Promise.resolve(data)                              // o mês responde na hora, com total 99
      return new Promise((resolve) => slow.push(() => resolve(data)))        // a semana só responde quando liberarmos, com total 11
    })
    await mountView(DailyBreakdown)
    expect(slow.length).toBe(2)                                              // by-day e revenue da semana estão pendentes
    await click('.breakdown button', 'Mês')
    const footer = () => norm(document.querySelector('.breakdown tfoot').textContent)
    expect(footer()).toContain('99')                                         // o mês já apareceu
    slow.forEach((release) => release()); await flushPromises()              // agora a resposta ANTIGA (semana) chega atrasada
    expect(footer()).toContain('99')
    expect(footer()).not.toMatch(/\b11\b/)                                  // e não pode sobrescrever o mês
  })

  it('mostra o erro em vez de dados quando a consulta falha', async () => {
    api.mockRejectedValue(Object.assign(new Error('Sem conexão com o servidor.'), { status: 0 }))
    const w = await mountView(DailyBreakdown)
    expect(norm(w.text())).toContain('Sem conexão com o servidor.')
    expect(document.querySelector('.breakdown table')).toBeNull()
  })

  it('avisa, no ícone de informação, que o faturamento conta só os concluídos', async () => {
    backend()
    await mountView(DailyBreakdown)
    const info = document.querySelector('.breakdown .info')
    expect(info.getAttribute('title')).toBe('Faturamento = atendimentos concluídos.')
    expect(info.getAttribute('aria-label')).toBe('Faturamento = atendimentos concluídos.')
  })
})
