import { describe, expect, it } from 'vitest'
import { formatBRL, formatDayMonth, formatPercent } from './format'
import { daysBetween, presetRange } from './period'

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
