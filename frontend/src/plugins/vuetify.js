import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'

export const THEME_KEY = 'barbearia_theme'

// Preferência salva ('light' | 'dark'); sem ela, segue o tema do sistema operacional.
export function savedTheme() {
  try { const v = localStorage.getItem(THEME_KEY); return v === 'light' || v === 'dark' ? v : null } catch { return null }
}
export function saveTheme(name) {
  try { localStorage.setItem(THEME_KEY, name) } catch { /* ignora */ }
}

// Paleta: tinta (azul-petróleo escuro) + latão. Fundo "papel" no claro, grafite azulado no escuro.
const light = {
  dark: false,
  colors: {
    background: '#f5f2ec', surface: '#ffffff', 'surface-variant': '#ece7dd',
    primary: '#1c2b3a', secondary: '#a97c2f', accent: '#a97c2f',
    success: '#2f7d5c', warning: '#b7791f', error: '#b4342a', info: '#2c6a8f', neutral: '#a39d92',
  },
}
const dark = {
  dark: true,
  colors: {
    background: '#0e1218', surface: '#171d27', 'surface-variant': '#222a37',
    primary: '#d7ae62', 'on-primary': '#1a1408', secondary: '#7fa3c7', accent: '#d7ae62',
    success: '#5fc08f', warning: '#e3a94d', error: '#ec7a6c', info: '#7fb2d6', neutral: '#6b7383',
  },
}

export default createVuetify({
  theme: { defaultTheme: savedTheme() ?? 'system', themes: { light, dark } },
  defaults: {
    VCard: { rounded: 'lg', elevation: 0, border: true },
    VBtn: { rounded: 'md', elevation: 0 },
    VTextField: { variant: 'outlined', density: 'comfortable' },
    VSelect: { variant: 'outlined', density: 'comfortable' },
    VAutocomplete: { variant: 'outlined', density: 'comfortable' },
    VTextarea: { variant: 'outlined', density: 'comfortable' },
    VChip: { rounded: 'md' },
  },
})
