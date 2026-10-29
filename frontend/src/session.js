// Quem está logado. Carregado uma vez de /auth/me e consultado pelo roteador e pelo layout.
import { reactive } from 'vue'
import { api } from './api'

export const session = reactive({ user: null, loaded: false })

export async function loadUser({ force = false } = {}) {
  if (session.loaded && !force) return session.user
  try {
    session.user = await api('/auth/me')
  } catch {
    session.user = null   // token inválido/expirado: o cliente HTTP já cuida de voltar ao login
  }
  session.loaded = true
  return session.user
}

// Chamado ao entrar ou sair, para uma pessoa nunca herdar os dados da anterior.
export function resetSession() {
  session.user = null
  session.loaded = false
}
