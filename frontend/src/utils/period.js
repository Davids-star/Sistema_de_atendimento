// Períodos pré-definidos do dashboard. Trabalha com datas 'AAAA-MM-DD' sem fuso.
const pad = (n) => String(n).padStart(2, '0')
export const toISO = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

export function presetRange(name, today = new Date()) {
  const y = today.getFullYear()
  const m = today.getMonth()
  if (name === 'this_month') return { from: toISO(new Date(y, m, 1)), to: toISO(new Date(y, m + 1, 0)) }
  if (name === 'last_month') return { from: toISO(new Date(y, m - 1, 1)), to: toISO(new Date(y, m, 0)) }
  if (name === 'last_30') {
    const start = new Date(y, m, today.getDate() - 29)
    return { from: toISO(start), to: toISO(today) }
  }
  throw new Error(`Período desconhecido: ${name}`)
}

export function daysBetween(from, to) {
  const [fy, fm, fd] = from.split('-').map(Number)
  const [ty, tm, td] = to.split('-').map(Number)
  return Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / 86400000) + 1
}
