import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'

export default createVuetify({
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: { primary: '#1f3a5f', secondary: '#8a6d3b', background: '#f4f5f7' },
      },
    },
  },
  defaults: {
    VCard: { rounded: 'lg', elevation: 1 },
    VBtn: { rounded: 'md' },
    VTextField: { variant: 'outlined', density: 'comfortable' },
  },
})
