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

// Paleta neutra: cinzas quentes + ardósia, com verde-sálvia suave como destaque. Serve para qualquer negócio.
const light = {
  dark: false,
  colors: {
    background: '#f5f4f1', surface: '#ffffff', 'surface-variant': '#ebe9e4',
    primary: '#34444f', secondary: '#5f8b7e', accent: '#5f8b7e',
    success: '#2f7d5c', warning: '#b7791f', error: '#b4342a', info: '#2c6a8f', neutral: '#a39d92',
  },
}
const dark = {
  dark: true,
  colors: {
    background: '#101418', surface: '#181e24', 'surface-variant': '#232b33',
    primary: '#9fc3b8', 'on-primary': '#0f1f1a', secondary: '#86a9c4', accent: '#9fc3b8',
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
