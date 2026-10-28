// Funções puras de formatação (fáceis de testar).
const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export const formatBRL = (cents) => brl.format((cents ?? 0) / 100)

// A API devolve a taxa como fração (0.2) ou null quando não há base de cálculo.
export const formatPercent = (rate) =>
  rate === null || rate === undefined ? '—' : `${(rate * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`

// '2029-03-05' -> '05/03'. Não usa Date para não sofrer com fuso horário.
export const formatDayMonth = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
