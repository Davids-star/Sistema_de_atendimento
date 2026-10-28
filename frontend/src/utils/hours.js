// Validação do horário de funcionamento (espelha as regras da API, para avisar antes de enviar).
export const WEEKDAYS = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']

// "09:00:00" -> "09:00"
export const trimTime = (t) => (t ?? '').slice(0, 5)

// Recebe [{start, end}] de um dia e devolve a mensagem do primeiro problema ('' se estiver tudo certo).
export function validateIntervals(intervals) {
  for (const { start, end } of intervals) {
    if (!start || !end) return 'Preencha o início e o fim de cada intervalo.'
    if (start >= end) return 'O início deve ser anterior ao fim.'
  }
  const sorted = [...intervals].sort((a, b) => a.start.localeCompare(b.start))
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].start < sorted[i - 1].end) return 'Os intervalos do mesmo dia não podem se sobrepor.'
  }
  return ''
}

// Lista da API -> { 0: [{start,end}], ..., 6: [...] }
export function groupByWeekday(items) {
  const days = Object.fromEntries([0, 1, 2, 3, 4, 5, 6].map((d) => [d, []]))
  for (const it of items) days[it.weekday].push({ start: trimTime(it.start_time), end: trimTime(it.end_time) })
  for (const d of Object.values(days)) d.sort((a, b) => a.start.localeCompare(b.start))
  return days
}

// { 0: [...] } -> lista para enviar à API
export const flattenDays = (days) =>
  Object.entries(days).flatMap(([weekday, list]) => list.map((i) => ({ weekday: +weekday, start_time: i.start, end_time: i.end })))
