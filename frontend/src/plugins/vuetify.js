import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'

export const THEME_KEY = 'barbearia_theme'

// Preferência salva ('light' | 'dark'); sem ela, padrão 'light'.
export function savedTheme() {
  try {
    const v = localStorage.getItem(THEME_KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

export function saveTheme(name) {
  try {
    localStorage.setItem(THEME_KEY, name)
  } catch {
    /* ignora */
  }
}

// Paleta executiva e acolhedora: Vinho Tinto / Marsala e Bege Nude Quente.
const light = {
  dark: false,
  colors: {
    background: '#f8efe4',
    surface: '#ffffff',
    'surface-variant': '#f3e6d8',
    primary: '#6b1322',
    'on-primary': '#ffffff',
    secondary: '#c88a58',
    accent: '#8c2034',
    success: '#3c763d',
    warning: '#d97706',
    error: '#b22222',
    info: '#2c6a8f',
    neutral: '#8e757a',
  },
}

const dark = {
  dark: true,
  colors: {
    background: '#151012',
    surface: '#20161a',
    'surface-variant': '#2d1e24',
    primary: '#e07a8b',
    'on-primary': '#2a050d',
    secondary: '#dfa87e',
    accent: '#e07a8b',
    success: '#5fc08f',
    warning: '#e3a94d',
    error: '#ec7a6c',
    info: '#7fb2d6',
    neutral: '#9d878d',
  },
}

export default createVuetify({
  theme: {
    defaultTheme: savedTheme() ?? 'light',
    themes: { light, dark },
  },
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
