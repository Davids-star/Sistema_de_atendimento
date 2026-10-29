import { describe, expect, it } from 'vitest'
import { centsToInput, formatDuration, formatPhone, parseBRL } from './format'
import { addDays, dayOf, formatDayLong, startOfWeek, timeAgo, timeOf } from './datetime'

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

describe('timeAgo', () => {
  const now = new Date('2029-03-10T15:00:00Z')   // 12:00 em São Paulo
  it.each([
    ['2029-03-10T14:59:40Z', 'agora'],
    ['2029-03-10T14:55:00Z', 'há 5 min'],
    ['2029-03-10T14:01:00Z', 'há 59 min'],
    ['2029-03-10T13:00:00Z', 'há 2 h'],
    ['2029-03-10T09:00:00Z', 'há 6 h'],
    ['2029-03-09T20:00:00Z', 'ontem'],
    ['2029-03-08T20:00:00Z', '08/03 17:00'],
  ])('%s -> %s', (iso, expected) => expect(timeAgo(iso, now)).toBe(expected))
  it('data no futuro (relógio diferente) não quebra', () => expect(timeAgo('2029-03-10T16:00:00Z', now)).toBe('agora'))
  it('virada de dia: 23:50 de ontem, às 00:10 de hoje, é "ontem" e não "há 0 h"', () => {
    expect(timeAgo('2029-03-10T02:50:00Z', new Date('2029-03-10T03:10:00Z'))).toBe('há 20 min')   // 23:50 -> 00:10 locais
    expect(timeAgo('2029-03-09T20:00:00Z', new Date('2029-03-10T03:10:00Z'))).toBe('ontem')
  })
})
