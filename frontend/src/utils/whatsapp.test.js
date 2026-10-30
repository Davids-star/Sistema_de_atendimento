import { describe, expect, it } from 'vitest'
import { appointmentMessage, appointmentWhatsappLink, whatsappLink } from './whatsapp'

const appt = (over = {}) => ({ client_name: 'Maria da Silva', client_phone: '5511977776666', service_name: 'Manicure',
  starts_at: '2030-01-07T17:00:00Z', status: 'confirmed', ...over })   // 17:00Z = seg 14:00 em São Paulo

describe('whatsappLink', () => {
  it('monta o link oficial com o número só em dígitos e o texto codificado', () => {
    expect(whatsappLink('5511977776666', 'Olá! Tudo bem?')).toBe('https://wa.me/5511977776666?text=Ol%C3%A1!%20Tudo%20bem%3F')
  })
  it('sem texto, abre só a conversa', () => expect(whatsappLink('5511977776666')).toBe('https://wa.me/5511977776666'))
  it('aceita celular (13 dígitos) e fixo (12 dígitos)', () => {
    expect(whatsappLink('5511977776666')).toContain('5511977776666'); expect(whatsappLink('551133334444')).toContain('551133334444')
  })
  it('limpa formatação que tenha sobrado no número', () => expect(whatsappLink('+55 (11) 97777-6666')).toBe('https://wa.me/5511977776666'))
  it.each([null, undefined, '', '123', 'abc', '11977776666', '5511', '+1 415 555 2671', '55119777766669999', '551197777666a'])(
    'número inválido (%s) não gera link', (p) => expect(whatsappLink(p, 'oi')).toBeNull())
  it('texto malicioso não escapa da URL (& # ? e quebras de linha viram %XX)', () => {
    const link = whatsappLink('5511977776666', 'a&phone=5599999999999#x?y\n<script>')
    expect(link).toBe('https://wa.me/5511977776666?text=a%26phone%3D5599999999999%23x%3Fy%0A%3Cscript%3E')
    expect(new URL(link).searchParams.get('phone')).toBeNull()               // não dá para injetar outro parâmetro (outro destinatário)
    expect(new URL(link).hostname).toBe('wa.me')
  })
})

describe('appointmentMessage', () => {
  it('pendente: pede a confirmação, com serviço, dia e hora no fuso do negócio', () => {
    const t = appointmentMessage(appt({ status: 'pending' }))
    expect(t).toContain('Olá, Maria!'); expect(t).toContain('Manicure, seg, 07/01 às 14:00'); expect(t).toContain('confirmar')
  })
  it('confirmado: lembra do horário', () => expect(appointmentMessage(appt())).toContain('Só lembrando do seu horário: Manicure, seg, 07/01 às 14:00'))
  it('cancelado: oferece remarcar', () => expect(appointmentMessage(appt({ status: 'cancelled' }))).toContain('que foi cancelado: gostaria de marcar outro horário?'))
  it('ausente: pergunta se quer remarcar', () => expect(appointmentMessage(appt({ status: 'no_show' }))).toContain('Sentimos a sua falta'))
  it('concluído: agradece', () => expect(appointmentMessage(appt({ status: 'completed' }))).toContain('Obrigado pela visita'))
  it('usa só o primeiro nome e funciona sem nome', () => {
    expect(appointmentMessage(appt({ client_name: '  Ana   Paula Souza ' }))).toContain('Olá, Ana!')
    expect(appointmentMessage(appt({ client_name: '' }))).toMatch(/^Olá! Aqui é do /)
  })
  it('menciona o nome do negócio configurado', () => expect(appointmentMessage(appt())).toContain('Aqui é do Agenda.'))
})

describe('appointmentWhatsappLink', () => {
  it('junta o número do cliente com a mensagem do agendamento', () => {
    const link = appointmentWhatsappLink(appt())
    expect(link.startsWith('https://wa.me/5511977776666?text=')).toBe(true)
    expect(decodeURIComponent(link.split('text=')[1])).toContain('Só lembrando do seu horário')
  })
  it('cliente com telefone inválido: sem link', () => expect(appointmentWhatsappLink(appt({ client_phone: '123' }))).toBeNull())
})
