// Datas e horas sempre no fuso da barbearia, não no do computador de quem olha.
export const SHOP_TZ = 'America/Sao_Paulo'

const partsFmt = new Intl.DateTimeFormat('en-CA', {
  timeZone: SHOP_TZ, year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})
function parts(iso) {
  const o = {}
  for (const p of partsFmt.formatToParts(new Date(iso))) o[p.type] = p.value
  return o
}

export const dayOf = (iso) => { const p = parts(iso); return `${p.year}-${p.month}-${p.day}` }   // '2029-03-05'
export const timeOf = (iso) => { const p = parts(iso); return `${p.hour}:${p.minute}` }          // '09:30'
export const todayISO = () => dayOf(new Date().toISOString())

export function addDays(day, n) {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10)
}

const WEEKDAYS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']
export const weekdayShort = (day) => WEEKDAYS[new Date(`${day}T12:00:00Z`).getUTCDay()]
export const formatDayLong = (day) => {
  const [y, m, d] = day.split('-')
  return `${weekdayShort(day)}, ${d}/${m}/${y}`
}
export const formatDateTime = (iso) => { const [y, m, d] = dayOf(iso).split('-'); return `${d}/${m}/${y} ${timeOf(iso)}` }

// Início (segunda-feira) da semana que contém `day`.
export function startOfWeek(day) {
  const dow = new Date(`${day}T12:00:00Z`).getUTCDay() // 0=dom
  return addDays(day, -((dow + 6) % 7))
}

// <input type="datetime-local"> (sem fuso) -> ISO com fuso. Assume que o navegador está no fuso da barbearia.
export const localInputToISO = (value) => new Date(value).toISOString()
export const isoToLocalInput = (iso) => { const p = parts(iso); return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}` }
