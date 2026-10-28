import '@fontsource-variable/inter'
import '@fontsource-variable/fraunces'
import { createApp } from 'vue'
import App from './App.vue'
import vuetify from './plugins/vuetify'
import './styles/app.css' // depois do Vuetify, para os nossos estilos prevalecerem
import router from './router'
import { setUnauthorizedHandler } from './api'

setUnauthorizedHandler(() => router.push({ name: 'login' }))

createApp(App).use(vuetify).use(router).mount('#app')
