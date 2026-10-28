import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({ api: vi.fn(), setToken: vi.fn() }))
import { api, setToken } from '../api'
import { bodyText, clickButton, mountView, typeInto } from '../test-helpers'
import ClientsView from './ClientsView.vue'
import ServicesView from './ServicesView.vue'
import SettingsView from './SettingsView.vue'

const calls = (method, part) => api.mock.calls.filter(([p, o]) => (o?.method ?? 'GET') === method && p.includes(part))
const SERVICES = [
  { id: 1, name: 'Corte', description: 'Tesoura ou máquina', price_cents: 4000, duration_minutes: 30, is_active: true },
  { id: 2, name: 'Barba', description: null, price_cents: 3000, duration_minutes: 90, is_active: false },
]
beforeEach(() => { api.mockReset(); document.body.innerHTML = '' })

describe('ServicesView', () => {
  const backend = () => api.mockImplementation(async (path, o = {}) => (path === '/services' && !o.method ? SERVICES : {}))

  it('lista serviços com preço, duração e situação', async () => {
    backend()
    await mountView(ServicesView)
    const t = bodyText()
    expect(t).toContain('Corte'); expect(t).toContain('R$ 40,00'); expect(t).toContain('30 min')
    expect(t).toContain('Barba'); expect(t).toContain('1 h 30 min'); expect(t).toContain('Inativo')
    expect(api).toHaveBeenCalledWith('/services', { params: { include_inactive: true } })
  })

  it('cria serviço convertendo o preço para centavos', async () => {
    backend()
    await mountView(ServicesView)
    await clickButton('Novo serviço')
    const inputs = [...document.querySelectorAll('.v-overlay--active input, .v-overlay--active textarea')]
    const save = () => [...document.querySelectorAll('.v-overlay--active button')].find((b) => b.textContent.trim() === 'Salvar')
    expect(save().disabled).toBe(true)                      // formulário vazio
    await typeInto(inputs[0], 'Pigmentação')
    await typeInto(inputs[2], '1.250,50')
    await typeInto(inputs[3], '45')
    expect(save().disabled).toBe(false)
    save().click(); await flushPromises()
    const [, opts] = calls('POST', '/services')[0]
    expect(opts.body).toEqual({ name: 'Pigmentação', description: null, price_cents: 125050, duration_minutes: 45 })
  })

  it('recusa preço inválido', async () => {
    backend()
    await mountView(ServicesView)
    await clickButton('Novo serviço')
    const inputs = [...document.querySelectorAll('.v-overlay--active input')]
    await typeInto(inputs[0], 'X'); await typeInto(inputs[1], 'abc')
    const save = [...document.querySelectorAll('.v-overlay--active button')].find((b) => b.textContent.trim() === 'Salvar')
    expect(save.disabled).toBe(true)
  })

  it('reativar chama PATCH is_active', async () => {
    backend()
    await mountView(ServicesView)
    document.querySelector('button[title="Reativar"]').click(); await flushPromises()
    expect(calls('PATCH', '/services/2')[0][1].body).toEqual({ is_active: true })
  })

  it('excluir pede confirmação e avisa quando só desativou', async () => {
    let deleted = false
    api.mockImplementation(async (path, o = {}) => {
      if (o.method === 'DELETE') { deleted = true; return null }
      return path === '/services' ? SERVICES : {}   // continua existindo => foi só desativado
    })
    await mountView(ServicesView)
    document.querySelector('button[title="Excluir"]').click(); await flushPromises()
    expect(bodyText()).toContain('apenas desativado')
    expect(deleted).toBe(false)
    await clickButton('Excluir'); await flushPromises()
    expect(deleted).toBe(true)
  })
})

describe('ClientsView', () => {
  const rows = (n) => Array.from({ length: n }, (_, i) => ({ id: i + 1, name: `Cliente ${i + 1}`, phone: '5511999998888', created_at: '' }))

  it('lista com telefone formatado', async () => {
    api.mockResolvedValue(rows(2))
    await mountView(ClientsView)
    expect(bodyText()).toContain('Cliente 1'); expect(bodyText()).toContain('(11) 99999-8888')
    expect(bodyText()).not.toContain('Cliente 3')
  })

  it('pagina: pede um registro a mais para saber se há próxima página', async () => {
    api.mockResolvedValue(rows(21))
    await mountView(ClientsView)
    expect(api.mock.calls[0][1].params).toMatchObject({ limit: 21, offset: 0 })
    expect(bodyText()).not.toContain('Cliente 21')                 // só 20 aparecem
    const next = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Próxima'))
    expect(next.disabled).toBe(false)
    next.click(); await flushPromises()
    expect(api.mock.calls.at(-1)[1].params.offset).toBe(20)
  })

  it('estado vazio', async () => {
    api.mockResolvedValue([])
    await mountView(ClientsView)
    expect(bodyText()).toContain('Nenhum cliente cadastrado ainda')
  })
})

describe('SettingsView', () => {
  const backend = () => api.mockImplementation(async (path, o = {}) => {
    if (path === '/settings') return { slot_interval_minutes: o.body?.slot_interval_minutes ?? 45 }
    if (path === '/business-hours') return o.method === 'PUT' ? o.body.items : [{ weekday: 0, start_time: '09:00:00', end_time: '12:00:00' }]
    if (path === '/blocked-times') return []
    return {}
  })

  it('carrega intervalo, horários e mostra dias fechados', async () => {
    backend()
    await mountView(SettingsView)
    const t = bodyText()
    expect(t).toContain('Segunda-feira'); expect(t).toContain('Domingo')
    expect(t).toContain('Fechado')
    expect(document.querySelector('input[type="time"]').value).toBe('09:00')
    expect(document.querySelector('input[type="number"]').value).toBe('45')
  })

  it('salva o intervalo definido pelo admin', async () => {
    backend()
    await mountView(SettingsView)
    await clickButton('60 min')
    await clickButton('Salvar')
    expect(calls('PUT', '/settings')[0][1].body).toEqual({ slot_interval_minutes: 60 })
  })

  it('bloqueia o salvamento com intervalos sobrepostos', async () => {
    backend()
    await mountView(SettingsView)
    document.querySelectorAll('button')[0]
    const addBtn = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Intervalo'))
    addBtn.click(); await flushPromises()                       // 2º intervalo na segunda: 09:00–18:00 (sobrepõe 09–12)
    expect(bodyText()).toContain('não podem se sobrepor')
    const save = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Salvar horários'))
    expect(save.disabled).toBe(true)
  })

  it('envia o horário válido no formato da API', async () => {
    backend()
    await mountView(SettingsView)
    await clickButton('Salvar horários')
    expect(calls('PUT', '/business-hours')[0][1].body).toEqual({ items: [{ weekday: 0, start_time: '09:00', end_time: '12:00' }] })
  })

  describe('alterar senha', () => {
    const open = async (me = { has_password: true }) => {
      api.mockImplementation(async (path, o = {}) => {
        if (path === '/auth/me') return me
        if (path === '/auth/change-password') return { access_token: 'token-novo' }
        if (path === '/settings') return { slot_interval_minutes: 30 }
        if (path === '/business-hours' || path === '/blocked-times') return []
        return {}
      })
      await mountView(SettingsView)
    }
    const inputs = () => [...document.querySelectorAll('.pw-form input')]
    const submit = () => [...document.querySelectorAll('.pw-form button')].find((b) => /senha/i.test(b.textContent))

    it('envia senha atual e nova, e guarda o token novo', async () => {
      await open()
      const [cur, nw, conf] = inputs()
      await typeInto(cur, 'senha-antiga-123'); await typeInto(nw, 'senha-nova-forte-1'); await typeInto(conf, 'senha-nova-forte-1')
      expect(submit().disabled).toBe(false)
      submit().click(); await flushPromises()
      expect(calls('POST', '/auth/change-password')[0][1].body).toEqual({ current_password: 'senha-antiga-123', new_password: 'senha-nova-forte-1' })
      expect(setToken).toHaveBeenCalledWith('token-novo')
    })

    it('não deixa enviar com senha curta ou confirmação diferente', async () => {
      await open()
      const [cur, nw, conf] = inputs()
      await typeInto(cur, 'senha-antiga-123'); await typeInto(nw, 'curta'); await typeInto(conf, 'curta')
      expect(submit().disabled).toBe(true)
      await typeInto(nw, 'senha-nova-forte-1')
      expect(submit().disabled).toBe(true)      // confirmação ainda é "curta"
      expect(bodyText()).toContain('As senhas não conferem')
    })

    it('exige a senha atual quando o admin já tem senha', async () => {
      await open()
      const [, nw, conf] = inputs()
      await typeInto(nw, 'senha-nova-forte-1'); await typeInto(conf, 'senha-nova-forte-1')
      expect(submit().disabled).toBe(true)
    })

    it('admin só-Google não precisa de senha atual e vê "Criar senha"', async () => {
      await open({ has_password: false })
      expect(inputs()).toHaveLength(2)
      expect(bodyText()).toContain('Criar senha')
      const [nw, conf] = inputs()
      await typeInto(nw, 'senha-nova-forte-1'); await typeInto(conf, 'senha-nova-forte-1')
      submit().click(); await flushPromises()
      expect(calls('POST', '/auth/change-password')[0][1].body).toEqual({ current_password: null, new_password: 'senha-nova-forte-1' })
    })
  })
})
