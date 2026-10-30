// Abre uma conversa no WhatsApp já com a mensagem pronta (link oficial wa.me). A pessoa só toca em "enviar".
import { BRAND } from '../brand'
import { formatDayMonth } from './format'
import { timeOf, weekdayShort, dayOf } from './datetime'

// O número vem do banco no formato 5511999998888. wa.me exige só dígitos, com o código do país. Fora disso: sem link.
export function whatsappLink(phone, text) {
  const raw = String(phone ?? '')
  if (!/^[\d\s()+.\-]+$/.test(raw)) return null   // só dígitos e formatação comum: um número com letras é lixo, não "adivinhar" o resto
  const digits = raw.replace(/\D/g, '')
  if (!/^\d{12,13}$/.test(digits) || !digits.startsWith('55')) return null
  return `https://wa.me/${digits}` + (text ? `?text=${encodeURIComponent(text)}` : '')
}

const firstName = (name) => String(name ?? '').trim().split(/\s+/)[0] || ''

// "sex, 30/10 às 09:00" (no fuso do negócio)
const when = (iso) => { const d = dayOf(iso); return `${weekdayShort(d)}, ${formatDayMonth(d)} às ${timeOf(iso)}` }

// Texto pronto conforme o estado do agendamento. É só uma sugestão: a pessoa pode editar antes de enviar.
export function appointmentMessage(a) {
  const hello = `Olá${firstName(a.client_name) ? `, ${firstName(a.client_name)}` : ''}! Aqui é do ${BRAND.name}.`
  const what = `${a.service_name}, ${when(a.starts_at)}`
  switch (a.status) {
    case 'pending': return `${hello} Passando para confirmar o seu horário: ${what}. Tudo certo para você?`
    case 'confirmed': return `${hello} Só lembrando do seu horário: ${what}. Qualquer imprevisto, é só avisar por aqui.`
    case 'cancelled': return `${hello} Sobre o seu agendamento de ${what}, que foi cancelado: gostaria de marcar outro horário?`
    case 'no_show': return `${hello} Sentimos a sua falta no horário de ${what}. Quer remarcar?`
    default: return `${hello} Obrigado pela visita! Quando quiser marcar um novo horário, é só falar por aqui.`
  }
}

export const appointmentWhatsappLink = (a) => whatsappLink(a.client_phone, appointmentMessage(a))


// Mensagem do dono para quem pediu atendimento (abre o WhatsApp da cliente já escrita).
export const handoffMessage = (name) =>
  `Olá${firstName(name) ? `, ${firstName(name)}` : ''}! Aqui é do ${BRAND.name}. Vi que você pediu para falar com a gente. Como posso ajudar?`
