import { describe, expect, it } from 'vitest'
import { flattenDays, groupByWeekday, validateIntervals } from './hours'

describe('validateIntervals', () => {
  it('aceita pausa de almoço', () => expect(validateIntervals([{ start: '09:00', end: '12:00' }, { start: '14:00', end: '18:00' }])).toBe(''))
  it('aceita intervalos encostados', () => expect(validateIntervals([{ start: '09:00', end: '12:00' }, { start: '12:00', end: '18:00' }])).toBe(''))
  it('recusa início depois do fim', () => expect(validateIntervals([{ start: '12:00', end: '09:00' }])).toMatch(/anterior/))
  it('recusa iguais', () => expect(validateIntervals([{ start: '09:00', end: '09:00' }])).toMatch(/anterior/))
  it('recusa vazio', () => expect(validateIntervals([{ start: '', end: '10:00' }])).toMatch(/Preencha/))
  it('recusa sobreposição, mesmo fora de ordem', () =>
    expect(validateIntervals([{ start: '11:00', end: '13:00' }, { start: '09:00', end: '12:00' }])).toMatch(/sobrepor/))
  it('dia sem intervalos é válido (fechado)', () => expect(validateIntervals([])).toBe(''))
})

describe('agrupamento', () => {
  it('ida e volta com a API', () => {
    const api = [
      { weekday: 0, start_time: '14:00:00', end_time: '18:00:00' },
      { weekday: 0, start_time: '09:00:00', end_time: '12:00:00' },
      { weekday: 5, start_time: '09:00:00', end_time: '13:00:00' },
    ]
    const days = groupByWeekday(api)
    expect(days[0]).toEqual([{ start: '09:00', end: '12:00' }, { start: '14:00', end: '18:00' }])
    expect(days[1]).toEqual([])
    expect(flattenDays(days)).toEqual([
      { weekday: 0, start_time: '09:00', end_time: '12:00' },
      { weekday: 0, start_time: '14:00', end_time: '18:00' },
      { weekday: 5, start_time: '09:00', end_time: '13:00' },
    ])
  })
})
