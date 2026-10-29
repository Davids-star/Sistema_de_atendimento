import { describe, expect, it } from 'vitest'
import { formatBRL, formatDayMonth, formatPercent } from './format'
import { daysBetween, presetRange, shiftAnchor, viewRange, weekBuckets } from './period'

const norm = (s) => s.replace(/ /g, ' ') // Intl usa espaço não separável

describe('format', () => {
  it('formata centavos em reais', () => {
    expect(norm(formatBRL(15500))).toBe('R$ 155,00')
    expect(norm(formatBRL(0))).toBe('R$ 0,00')
    expect(norm(formatBRL(null))).toBe('R$ 0,00')
  })
  it('formata taxa e trata ausência de dados', () => {
    expect(formatPercent(0.2)).toBe('20%')
    expect(formatPercent(0.1234)).toBe('12,3%')
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(0)).toBe('0%')
  })
  it('formata dia/mês sem depender de fuso', () => {
    expect(formatDayMonth('2029-03-05')).toBe('05/03')
  })
})

describe('period', () => {
  const today = new Date(2029, 2, 15) // 15/03/2029
  it('mês atual e anterior', () => {
    expect(presetRange('this_month', today)).toEqual({ from: '2029-03-01', to: '2029-03-31' })
    expect(presetRange('last_month', today)).toEqual({ from: '2029-02-01', to: '2029-02-28' })
  })
  it('virada de ano', () => {
    expect(presetRange('last_month', new Date(2030, 0, 10))).toEqual({ from: '2029-12-01', to: '2029-12-31' })
  })
  it('últimos 30 dias inclui hoje', () => {
    const r = presetRange('last_30', today)
    expect(r).toEqual({ from: '2029-02-14', to: '2029-03-15' })
    expect(daysBetween(r.from, r.to)).toBe(30)
  })
  it('hoje e esta semana (segunda a domingo)', () => {
    expect(presetRange('today', today)).toEqual({ from: '2029-03-15', to: '2029-03-15' })
    expect(presetRange('this_week', today)).toEqual({ from: '2029-03-12', to: '2029-03-18' })   // quinta 15/03
  })
  it('semana: segunda, domingo e virada de mês/ano', () => {
    expect(presetRange('this_week', new Date(2029, 2, 12))).toEqual({ from: '2029-03-12', to: '2029-03-18' })   // segunda
    expect(presetRange('this_week', new Date(2029, 2, 18))).toEqual({ from: '2029-03-12', to: '2029-03-18' })   // domingo
    expect(presetRange('this_week', new Date(2029, 3, 1))).toEqual({ from: '2029-03-26', to: '2029-04-01' })    // atravessa o mês
    expect(presetRange('this_week', new Date(2030, 0, 1))).toEqual({ from: '2029-12-31', to: '2030-01-06' })    // atravessa o ano
    expect(daysBetween(...Object.values(presetRange('this_week', today)))).toBe(7)
  })
  it('daysBetween', () => {
    expect(daysBetween('2029-03-01', '2029-03-31')).toBe(31)
    expect(daysBetween('2029-03-05', '2029-03-05')).toBe(1)
  })
})

describe('visão do dia a dia (dia, semana, mês)', () => {
  it('dia, semana (seg-dom) e mês', () => {
    expect(viewRange('day', '2029-03-15')).toMatchObject({ from: '2029-03-15', to: '2029-03-15', label: '15/03/2029' })
    expect(viewRange('week', '2029-03-15')).toMatchObject({ from: '2029-03-12', to: '2029-03-18', label: '12/03 – 18/03' })
    expect(viewRange('week', '2029-03-18')).toMatchObject({ from: '2029-03-12', to: '2029-03-18' })      // domingo
    expect(viewRange('month', '2029-03-15')).toMatchObject({ from: '2029-03-01', to: '2029-03-31', label: 'março de 2029' })
  })
  it('fevereiro de ano bissexto e não bissexto', () => {
    expect(viewRange('month', '2028-02-10').to).toBe('2028-02-29')
    expect(viewRange('month', '2029-02-10').to).toBe('2029-02-28')
  })
  it('anda um dia, uma semana ou um mês, inclusive virando o mês e o ano', () => {
    expect(shiftAnchor('day', '2029-03-31', 1)).toBe('2029-04-01')
    expect(shiftAnchor('day', '2029-01-01', -1)).toBe('2028-12-31')
    expect(shiftAnchor('week', '2029-03-15', 1)).toBe('2029-03-22')
    expect(shiftAnchor('week', '2029-03-15', -1)).toBe('2029-03-08')
    expect(shiftAnchor('month', '2029-03-15', 1)).toBe('2029-04-01')
    expect(shiftAnchor('month', '2029-12-20', 1)).toBe('2030-01-01')
    expect(shiftAnchor('month', '2029-01-20', -1)).toBe('2028-12-01')
  })
  it('mês: avançar a partir do dia 31 nunca cai em dia inexistente', () => {
    expect(shiftAnchor('month', '2029-01-31', 1)).toBe('2029-02-01')
    expect(viewRange('month', shiftAnchor('month', '2029-01-31', 1)).to).toBe('2029-02-28')
  })
  it('ida e volta volta ao mesmo lugar', () => {
    for (const mode of ['day', 'week']) expect(shiftAnchor(mode, shiftAnchor(mode, '2029-03-15', 1), -1)).toBe('2029-03-15')
  })
  it('semanas do mês cobrem todos os dias exatamente uma vez', () => {
    for (const month of ['2026-10-10', '2026-06-10', '2027-02-10', '2028-02-10', '2029-12-10']) {
      const { from, to } = viewRange('month', month)
      const buckets = weekBuckets(from, to)
      expect(buckets.length).toBeLessThanOrEqual(6)
      expect(buckets[0].from).toBe(from); expect(buckets.at(-1).to).toBe(to)
      expect(buckets.reduce((n, b) => n + daysBetween(b.from, b.to), 0)).toBe(daysBetween(from, to))
      for (let i = 1; i < buckets.length; i++) expect(daysBetween(buckets[i - 1].to, buckets[i].from)).toBe(2)   // sem lacunas
    }
  })
  it('semanas de outubro de 2026 (começa numa quinta)', () => {
    expect(weekBuckets('2026-10-01', '2026-10-31').map((b) => b.label)).toEqual(['01–04/10', '05–11/10', '12–18/10', '19–25/10', '26–31/10'])
  })
  it('um dia só vira um rótulo simples', () => {
    expect(weekBuckets('2026-11-30', '2026-11-30')[0].label).toBe('30/11')
  })
})
