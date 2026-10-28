import { describe, expect, it } from 'vitest'
import { availableActions, buildCreateBody, buildUpdateBody, isCreateValid, warningsText } from './appointments'

const NOW = new Date('2029-03-05T15:00:00Z')
const appt = (status, startsAt = '2029-03-05T14:00:00Z') => ({ status, starts_at: startsAt })

describe('availableActions', () => {
  it('pendente futuro: confirmar e cancelar', () => {
    expect(availableActions(appt('pending', '2029-03-05T18:00:00Z'), NOW)).toEqual(['confirm', 'cancel'])
  })
  it('confirmado futuro: só cancelar (concluir só depois do início)', () => {
    expect(availableActions(appt('confirmed', '2029-03-05T18:00:00Z'), NOW)).toEqual(['cancel'])
  })
  it('confirmado que já começou: concluir, não veio, cancelar', () => {
    expect(availableActions(appt('confirmed'), NOW)).toEqual(['complete', 'no_show', 'cancel'])
  })
  it('pendente que já começou: pode confirmar também', () => {
    expect(availableActions(appt('pending'), NOW)).toEqual(['confirm', 'complete', 'no_show', 'cancel'])
  })
  it.each(['completed', 'no_show', 'cancelled'])('%s não tem ações', (s) => expect(availableActions(appt(s), NOW)).toEqual([]))
})

describe('corpo das requisições', () => {
  const base = { serviceId: 3, startsAt: '2029-03-05T12:00:00Z', notes: '  ', status: 'confirmed' }
  it('cliente existente', () => {
    expect(buildCreateBody({ ...base, mode: 'existing', client: { id: 9 } })).toEqual(
      { service_id: 3, starts_at: base.startsAt, notes: null, status: 'confirmed', client_id: 9 })
  })
  it('cliente novo', () => {
    expect(buildCreateBody({ ...base, mode: 'new', phone: '(11) 99999-8888', name: ' Ana ' })).toEqual(
      { service_id: 3, starts_at: base.startsAt, notes: null, status: 'confirmed', client_phone: '(11) 99999-8888', client_name: 'Ana' })
  })
  it('validação', () => {
    expect(isCreateValid({ ...base, mode: 'existing', client: null })).toBe(false)
    expect(isCreateValid({ ...base, mode: 'existing', client: { id: 1 } })).toBe(true)
    expect(isCreateValid({ ...base, mode: 'new', name: 'Ana', phone: '123' })).toBe(false)
    expect(isCreateValid({ ...base, mode: 'new', name: 'Ana', phone: '11999998888' })).toBe(true)
    expect(isCreateValid({ ...base, mode: 'existing', client: { id: 1 }, startsAt: '' })).toBe(false)
  })
  it('update envia só o que mudou', () => {
    const orig = { starts_at: '2029-03-05T12:00:00Z', service_id: 3, notes: 'x' }
    const same = { startsAt: '2029-03-05T12:00:00.000Z', serviceId: 3, notes: 'x' }
    expect(buildUpdateBody(orig, same)).toEqual({})
    expect(buildUpdateBody(orig, { ...same, startsAt: '2029-03-05T13:00:00Z' })).toEqual({ starts_at: '2029-03-05T13:00:00Z' })
    expect(buildUpdateBody(orig, { ...same, serviceId: 4, notes: '' })).toEqual({ service_id: 4, notes: null })
  })
  it('avisos', () => {
    expect(warningsText([])).toBe('')
    expect(warningsText(['Fora do horário de funcionamento'])).toContain('Fora do horário de funcionamento')
  })
})
