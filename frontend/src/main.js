import '@fontsource-variable/inter'
import '@fontsource-variable/fraunces'
import { createApp } from 'vue'
import App from './App.vue'
import vuetify from './plugins/vuetify'
import './styles/app.css' // depois do Vuetify, para os nossos estilos prevalecerem
import router from './router'
import { setUnauthorizedHandler } from './api'
import { BRAND } from './brand'
import { resetSession } from './session'

setUnauthorizedHandler(() => { resetSession(); router.push({ name: 'login' }) })

document.title = BRAND.name

createApp(App).use(vuetify).use(router).mount('#app')
