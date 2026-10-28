// Mesma regra do backend (mínimo de 10 caracteres). A API continua sendo quem decide.
export const MIN_PASSWORD = 10

// Devolve a mensagem do primeiro problema, ou '' se estiver tudo certo.
export function passwordError(password, confirm) {
  if (!password) return 'Informe a nova senha.'
  if (password.length < MIN_PASSWORD) return `A senha deve ter pelo menos ${MIN_PASSWORD} caracteres.`
  if (confirm !== undefined && password !== confirm) return 'As senhas não conferem.'
  return ''
}
