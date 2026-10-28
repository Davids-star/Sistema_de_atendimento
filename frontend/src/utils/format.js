// Funções puras de formatação (fáceis de testar).
const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export const formatBRL = (cents) => brl.format((cents ?? 0) / 100)

// A API devolve a taxa como fração (0.2) ou null quando não há base de cálculo.
export const formatPercent = (rate) =>
  rate === null || rate === undefined ? '—' : `${(rate * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`

// '2029-03-05' -> '05/03'. Não usa Date para não sofrer com fuso horário.
export const formatDayMonth = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

// Converte o que a pessoa digitou ("40", "40,5", "1.234,56", "R$ 40,00") em centavos. Inválido -> null.
export function parseBRL(text) {
  let s = String(text ?? '').trim().replace(/^R\$\s*/, '')
  if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.')
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null
  return Math.round(parseFloat(s) * 100)
}

// Centavos -> texto para campo de edição: 4050 -> "40,50"
export const centsToInput = (cents) => ((cents ?? 0) / 100).toFixed(2).replace('.', ',')

// '5511999998888' -> '(11) 99999-8888'. Se não reconhecer o formato, devolve como veio.
export function formatPhone(phone) {
  const m = /^55(\d{2})(\d{4,5})(\d{4})$/.exec(phone ?? '')
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : phone ?? ''
}

export const formatDuration = (min) => {
  const h = Math.floor(min / 60)
  const m = min % 60
  return h ? (m ? `${h} h ${m} min` : `${h} h`) : `${m} min`
}
