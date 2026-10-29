// Identidade do painel. Para trocar o nome: VITE_APP_NAME=Meu Estúdio no .env do frontend (ou edite aqui).
export const BRAND = {
  name: import.meta.env.VITE_APP_NAME || 'Agenda',
  icon: 'mdi-calendar-heart',   // neutro: serve para qualquer negócio de agendamento
}
