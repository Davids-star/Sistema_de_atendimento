// Datas e horas sempre no fuso do negócio, não no do computador de quem olha.
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

// <input type="datetime-local"> (sem fuso) -> ISO com fuso. Assume que o navegador está no fuso do negócio.
export const localInputToISO = (value) => new Date(value).toISOString()
export const isoToLocalInput = (iso) => { const p = parts(iso); return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}` }


// "agora", "há 5 min", "há 2 h", "ontem", "28/10 14:05". `now` existe para os testes.
export function timeAgo(iso, now = new Date()) {
  const diff = Math.max(0, now.getTime() - new Date(iso).getTime())
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'agora'
  if (min < 60) return `há ${min} min`
  if (min < 24 * 60 && dayOf(iso) === dayOf(now.toISOString())) return `há ${Math.floor(min / 60)} h`
  if (dayOf(iso) === addDays(dayOf(now.toISOString()), -1)) return 'ontem'
  return formatDateTime(iso).slice(0, 5) + ' ' + timeOf(iso)
}
