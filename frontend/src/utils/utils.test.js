import { describe, expect, it } from 'vitest'
import { centsToInput, formatDuration, formatPhone, parseBRL } from './format'
import { addDays, dayOf, formatDayLong, startOfWeek, timeOf } from './datetime'

describe('parseBRL', () => {
  it.each([
    ['40', 4000], ['40,5', 4050], ['40,50', 4050], ['40.50', 4050], ['1.234,56', 123456], ['R$ 40,00', 4000], ['0', 0],
  ])('%s -> %s', (input, cents) => expect(parseBRL(input)).toBe(cents))
  it.each(['', 'abc', '-5', '1,234', '1.234', '4 0', null])('rejeita %s', (v) => expect(parseBRL(v)).toBeNull())
  it('ida e volta', () => expect(parseBRL(centsToInput(4050))).toBe(4050))
})

describe('formatPhone / duration', () => {
  it('formata celular e fixo', () => {
    expect(formatPhone('5511999998888')).toBe('(11) 99999-8888')
    expect(formatPhone('551133334444')).toBe('(11) 3333-4444')
    expect(formatPhone('123')).toBe('123')
  })
  it('duração', () => {
    expect(formatDuration(30)).toBe('30 min'); expect(formatDuration(60)).toBe('1 h'); expect(formatDuration(90)).toBe('1 h 30 min')
  })
})

describe('datetime (fuso do negócio)', () => {
  it('23:30 local não vira o dia seguinte', () => {
    expect(dayOf('2029-03-08T02:30:00Z')).toBe('2029-03-07')   // 23:30 em São Paulo
    expect(timeOf('2029-03-08T02:30:00Z')).toBe('23:30')
  })
  it('soma dias e acha a segunda-feira', () => {
    expect(addDays('2029-03-31', 1)).toBe('2029-04-01')
    expect(addDays('2029-03-01', -1)).toBe('2029-02-28')
    expect(startOfWeek('2029-03-07')).toBe('2029-03-05')   // quarta -> segunda
    expect(startOfWeek('2029-03-11')).toBe('2029-03-05')   // domingo -> segunda anterior
    expect(startOfWeek('2029-03-05')).toBe('2029-03-05')
  })
  it('dia da semana', () => expect(formatDayLong('2029-03-05')).toBe('seg, 05/03/2029'))
})
