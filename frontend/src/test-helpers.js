import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

export const norm = (s) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
export const bodyText = () => norm(document.body.textContent)

// Monta um componente dentro de <v-app> (necessário ao Vuetify). Diálogos ficam em document.body.
export async function mountView(Component, props = {}, extraPlugins = []) {
  const wrapper = mount(
    { template: '<v-app><C v-bind="p" /></v-app>', components: { C: Component }, data: () => ({ p: props }) },
    { global: { plugins: [createVuetify({ components, directives }), ...extraPlugins] }, attachTo: document.body },
  )
  await flushPromises()
  return wrapper
}

// Clica no primeiro botão (ou chip clicável) do documento cujo texto contém `text`.
export async function clickButton(text) {
  const btn = [...document.body.querySelectorAll('button, .v-chip')].find((b) => norm(b.textContent).includes(text))
  if (!btn) throw new Error(`Botão não encontrado: ${text}\n${bodyText().slice(0, 400)}`)
  btn.click()
  await flushPromises()
}

export const buttonTexts = () => [...document.body.querySelectorAll('button')].map((b) => norm(b.textContent))

export async function typeInto(input, value) {
  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await flushPromises()
}
