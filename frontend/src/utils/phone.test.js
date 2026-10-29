import { describe, expect, it } from 'vitest'
import { digitsOf, phoneError } from './phone'

describe('phone', () => {
  it.each(['(11) 99999-8888', '11999998888', '+55 11 99999-8888', '1133334444'])('aceita %s', (v) => expect(phoneError(v)).toBe(''))
  it.each(['', '123', 'abc', '119999', '55119999988889999'])('recusa %s', (v) => expect(phoneError(v)).not.toBe(''))
  it('digitsOf', () => expect(digitsOf('(11) 9-8888')).toBe('1198888'))
})
