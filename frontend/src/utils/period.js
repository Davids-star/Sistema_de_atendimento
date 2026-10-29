import { addDays, startOfWeek } from './datetime'

// Períodos pré-definidos do dashboard. Trabalha com datas 'AAAA-MM-DD' sem fuso.
const pad = (n) => String(n).padStart(2, '0')
export const toISO = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

export function presetRange(name, today = new Date()) {
  const y = today.getFullYear()
  const m = today.getMonth()
  if (name === 'today') return { from: toISO(today), to: toISO(today) }
  if (name === 'this_week') {   // segunda a domingo
    const start = new Date(y, m, today.getDate() - ((today.getDay() + 6) % 7))
    return { from: toISO(start), to: toISO(new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6)) }
  }
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


// ---------- visão do "Dia a dia": um dia, uma semana (seg-dom) ou um mês, com navegação ----------
const MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
const dm = (iso) => `${iso.slice(8)}/${iso.slice(5, 7)}`

export function viewRange(mode, anchor) {
  if (mode === 'day') return { from: anchor, to: anchor, label: dm(anchor) + '/' + anchor.slice(0, 4) }
  if (mode === 'week') {
    const from = startOfWeek(anchor)
    const to = addDays(from, 6)
    return { from, to, label: `${dm(from)} – ${dm(to)}` }
  }
  if (mode === 'month') {
    const [y, m] = anchor.split('-').map(Number)
    const last = new Date(Date.UTC(y, m, 0)).getUTCDate()
    return { from: `${y}-${String(m).padStart(2, '0')}-01`, to: `${y}-${String(m).padStart(2, '0')}-${String(last).padStart(2, '0')}`,
      label: `${MONTHS[m - 1]} de ${y}` }
  }
  throw new Error(`Modo desconhecido: ${mode}`)
}

// Anda um dia, uma semana ou um mês. No modo mês o ponto de referência vira o dia 1 (evita "31 + 1 mês" cair em dia inexistente).
export function shiftAnchor(mode, anchor, direction) {
  if (mode === 'day') return addDays(anchor, direction)
  if (mode === 'week') return addDays(anchor, 7 * direction)
  const [y, m] = anchor.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + direction, 1))
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-01`
}

// Quebra um período em semanas (seg-dom) cortadas nas pontas: serve para resumir um mês em poucas linhas.
export function weekBuckets(from, to) {
  const buckets = []
  let start = from
  while (start <= to) {
    const sunday = addDays(startOfWeek(start), 6)
    const end = sunday < to ? sunday : to
    buckets.push({ from: start, to: end, label: start === end ? dm(start) : `${start.slice(8)}–${end.slice(8)}/${end.slice(5, 7)}` })
    start = addDays(end, 1)
  }
  return buckets
}
