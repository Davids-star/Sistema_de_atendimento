// Cliente HTTP do painel. Todas as chamadas à API passam por aqui.
const TOKEN_KEY = 'barbearia_token'

// sessionStorage: o login some ao fechar a aba. Pode falhar (modo privado), por isso o try/catch.
function readToken() {
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}
function writeToken(value) {
  try { value ? sessionStorage.setItem(TOKEN_KEY, value) : sessionStorage.removeItem(TOKEN_KEY) } catch { /* ignora */ }
}

let token = readToken()
let onUnauthorized = () => {}

export const getToken = () => token
export const setToken = (value) => { token = value; writeToken(value) }
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

// O FastAPI devolve `detail` como texto, ou como lista nos erros de validação (422).
export function detailToMessage(detail, status) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  if (status === 429) return 'Muitas requisições. Aguarde um momento.'
  return 'Não foi possível concluir a operação.'
}

export async function api(path, { method = 'GET', params, body } = {}) {
  // No navegador a API está no mesmo endereço (o Vite/servidor encaminha). No app Android não: defina VITE_API_URL
  // (ex.: https://agenda.seudominio.com.br) ao gerar o app.
  const url = new URL(`${import.meta.env.VITE_API_URL || ''}/api/v1${path}`, window.location.origin)
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  }
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  } catch {
    throw new ApiError(0, 'Sem conexão com o servidor.')
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    // Token vencido ou inválido: volta para o login. (No próprio login, 401 é "senha errada".)
    if (res.status === 401 && token && path !== '/auth/login') {
      setToken(null)
      onUnauthorized()
    }
    throw new ApiError(res.status, detailToMessage(data?.detail, res.status))
  }
  return data
}
