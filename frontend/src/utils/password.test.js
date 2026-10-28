import { describe, expect, it } from 'vitest'
import { passwordError } from './password'

describe('passwordError', () => {
  it('aceita senha longa e igual à confirmação', () => expect(passwordError('uma-senha-forte-1', 'uma-senha-forte-1')).toBe(''))
  it('exige o mínimo de caracteres', () => expect(passwordError('curta', 'curta')).toMatch(/pelo menos 10/))
  it('aceita exatamente 10', () => expect(passwordError('1234567890', '1234567890')).toBe(''))
  it('exige confirmação igual', () => expect(passwordError('uma-senha-forte-1', 'outra-senha-forte')).toMatch(/não conferem/))
  it('vazia', () => expect(passwordError('', '')).toMatch(/Informe/))
  it('sem confirmação, só valida o tamanho', () => expect(passwordError('uma-senha-forte-1')).toBe(''))
})
