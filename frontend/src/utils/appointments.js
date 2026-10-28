// Regras do painel para agendamentos (espelham as da API; a API continua sendo quem decide).
export const ACTION_PATH = { confirm: 'confirm', cancel: 'cancel', complete: 'complete', no_show: 'no-show' }
export const ACTION_LABEL = { confirm: 'Confirmar', cancel: 'Cancelar', complete: 'Concluir', no_show: 'Não veio' }

export const isActive = (a) => a.status === 'pending' || a.status === 'confirmed'
export const canEdit = isActive

// Ações possíveis agora. "Concluir" e "Não veio" só depois que o horário começou.
export function availableActions(a, now = new Date()) {
  const out = []
  if (a.status === 'pending') out.push('confirm')
  if (isActive(a) && new Date(a.starts_at) <= now) out.push('complete', 'no_show')
  if (isActive(a)) out.push('cancel')
  return out
}

// Ações que pedem confirmação antes de executar (não dá para desfazer).
export const NEEDS_CONFIRMATION = new Set(['cancel', 'complete', 'no_show'])

export const CONFIRM_TEXT = {
  cancel: 'O horário voltará a ficar disponível.',
  complete: 'O atendimento entra no faturamento registrado.',
  no_show: 'O cliente será marcado como ausente e o horário ficará livre.',
}

const clean = (text) => text?.trim() || null

// f: { mode: 'existing'|'new', client: {id}|null, phone, name, serviceId, startsAt (ISO), notes, status }
export function buildCreateBody(f) {
  const body = { service_id: f.serviceId, starts_at: f.startsAt, notes: clean(f.notes), status: f.status }
  if (f.mode === 'existing') body.client_id = f.client.id
  else { body.client_phone = f.phone; body.client_name = f.name.trim() }
  return body
}

export function isCreateValid(f) {
  const clientOk = f.mode === 'existing' ? !!f.client : !!f.name?.trim() && (f.phone ?? '').replace(/\D/g, '').length >= 10
  return clientOk && !!f.serviceId && !!f.startsAt
}

// Só envia o que mudou (o PATCH da API altera apenas os campos recebidos).
export function buildUpdateBody(original, f) {
  const body = {}
  if (new Date(f.startsAt).getTime() !== new Date(original.starts_at).getTime()) body.starts_at = f.startsAt
  if (f.serviceId !== original.service_id) body.service_id = f.serviceId
  if (clean(f.notes) !== clean(original.notes)) body.notes = clean(f.notes)
  return body
}

// Avisos devolvidos pela API (ex.: fora do expediente) viram um texto só.
export const warningsText = (warnings) => (warnings?.length ? `Agendado, mas atenção: ${warnings.join('; ')}.` : '')
