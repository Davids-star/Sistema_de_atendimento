// Google Identity Services: o Google desenha o botão e entrega ao navegador um token assinado (credential).
// Nosso backend confere esse token; o frontend nunca decide quem é o usuário.
const SRC = 'https://accounts.google.com/gsi/client'
let loading = null

export function loadGoogleScript() {
  if (window.google?.accounts?.id) return Promise.resolve(window.google)
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = SRC
      s.async = true
      s.onload = () => resolve(window.google)
      s.onerror = () => { loading = null; reject(new Error('Não foi possível carregar o login do Google.')) }
      document.head.appendChild(s)
    })
  }
  return loading
}

export async function renderGoogleButton(element, clientId, onCredential) {
  const google = await loadGoogleScript()
  google.accounts.id.initialize({ client_id: clientId, callback: (r) => onCredential(r.credential) })
  google.accounts.id.renderButton(element, {
    type: 'standard', theme: 'outline', size: 'large', text: 'signin_with', shape: 'rectangular', locale: 'pt-BR',
    width: Math.min(400, element.clientWidth || 400),
  })
}
