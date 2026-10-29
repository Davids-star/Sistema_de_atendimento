// Validação leve de telefone no navegador (a API normaliza e valida de verdade).
export const digitsOf = (v) => (v ?? '').replace(/\D/g, '')

// Devolve a mensagem do problema, ou '' se parecer um telefone brasileiro (DDD + número, com ou sem 55).
export function phoneError(value) {
  const n = digitsOf(value).length
  return [10, 11, 12, 13].includes(n) ? '' : 'Informe DDD + número (ex.: 11 99999-8888)'
}
