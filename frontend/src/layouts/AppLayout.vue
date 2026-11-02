<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { api } from '../api'
import { BRAND } from '../brand'
import NotificationBell from '../components/NotificationBell.vue'
import { inbox, resetInbox, startPolling, stopPolling } from '../notifications'
import { setupPush } from '../push'
import { loadUser, session } from '../session'
import { toast } from '../utils/notify'

const router = useRouter()
const { mdAndUp } = useDisplay()
const admin = computed(() => session.user)
const adminFirstName = computed(() => admin.value?.name?.trim().split(/\s+/)[0] ?? '')
const pendingUsers = ref(0)   // só o dono vê: pessoas aguardando liberação

const fileInput = ref(null)
const userPhoto = ref('')
const userMenuOpen = ref(false)

function getStorageKey() {
  return `user_avatar_${admin.value?.id ?? 'default'}`
}

function loadUserPhoto() {
  try {
    const saved = localStorage.getItem(getStorageKey())
    userPhoto.value = saved || ''
  } catch {
    userPhoto.value = ''
  }
}

watch(() => admin.value?.id, loadUserPhoto, { immediate: true })

function triggerFileInput() {
  fileInput.value?.click()
}

function onFilePicked(event) {
  const file = event.target?.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    toast.show = true
    toast.text = 'Por favor, selecione um arquivo de imagem válido.'
    toast.color = 'error'
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    toast.show = true
    toast.text = 'Escolha uma imagem de até 2MB.'
    toast.color = 'error'
    return
  }
  const reader = new FileReader()
  reader.onload = (e) => {
    const result = e.target?.result
    if (typeof result === 'string') {
      userPhoto.value = result
      try {
        localStorage.setItem(getStorageKey(), result)
      } catch {
        // quota excedida ou storage restrito
      }
      toast.show = true
      toast.text = 'Foto de perfil atualizada!'
      toast.color = 'success'
    }
  }
  reader.readAsDataURL(file)
  if (event.target) event.target.value = ''
}

function removePhoto() {
  userPhoto.value = ''
  try {
    localStorage.removeItem(getStorageKey())
  } catch {}
  toast.show = true
  toast.text = 'Foto de perfil removida.'
  toast.color = 'info'
}

function goToSettings() {
  userMenuOpen.value = false
  router.push({ name: 'settings' })
}

const nav = [
  { title: 'Dashboard', icon: 'mdi-view-dashboard-outline', to: { name: 'dashboard' }, exact: true },
  { title: 'Agendamentos', icon: 'mdi-calendar-month-outline', to: { name: 'appointments' } },
  { title: 'Atendimento', icon: 'mdi-message-alert-outline', to: { name: 'handoff' }, badge: 'handoff' },
  { title: 'Serviços', icon: 'mdi-shimmer', to: { name: 'services' } },
  { title: 'Clientes', icon: 'mdi-account-multiple-outline', to: { name: 'clients' } },
  { title: 'Usuários', icon: 'mdi-shield-account-outline', to: { name: 'users' }, ownerOnly: true },
  { title: 'Configurações', icon: 'mdi-cog-outline', to: { name: 'settings' } },
]
// Quantos pedidos de atendimento ainda não lidos (vem dos avisos do sino).
const waiting = computed(() => inbox.items.filter((n) => n.kind === 'handoff' && !n.read_at).length)
const visibleNav = computed(() => nav.filter((i) => !i.ownerOnly || admin.value?.is_owner))
// Na barra móvel inferior removemos "Configurações", pois o acesso é feito pelo pop-up do avatar.
const mobileNav = computed(() => {
  const items = visibleNav.value.filter((i) => i.to.name !== 'settings')
  const order = admin.value?.is_owner
    ? ['appointments', 'clients', 'services', 'dashboard', 'handoff', 'users']
    : ['appointments', 'clients', 'dashboard', 'services', 'handoff']
  return items.sort((a, b) => order.indexOf(a.to.name) - order.indexOf(b.to.name))
})

onMounted(async () => {
  startPolling()   // avisos do sino enquanto o painel estiver aberto
  const user = await loadUser()   // 401 já redireciona para o login
  if (user) setupPush({ router })   // no app Android: pede permissão e registra o aparelho para receber avisos com o app fechado
  if (user?.is_owner) {
    try { pendingUsers.value = (await api('/users', { params: { status: 'pending_approval' } })).length } catch { /* só um aviso */ }
  }
})

onBeforeUnmount(stopPolling)
</script>

<template>
  <!-- Background decorativo superior -->
  <div class="top-wave-bg" aria-hidden="true">
    <svg viewBox="0 0 500 200" preserveAspectRatio="none" class="wave-svg">
      <path d="M150,0 C300,120 380,30 500,100 L500,0 L150,0 Z" fill="rgba(107, 19, 34, 0.08)"></path>
      <path d="M250,0 C360,140 420,50 500,140 L500,0 L250,0 Z" fill="rgba(107, 19, 34, 0.12)"></path>
      <path d="M380,0 C420,80 460,40 500,80 L500,0 L380,0 Z" fill="rgba(200, 138, 88, 0.15)"></path>
    </svg>
  </div>

  <!-- Sidebar fixa e expandida no computador. -->
  <v-navigation-drawer v-if="mdAndUp" permanent width="256" class="sidebar">
    <div class="brand">
      <div class="brand-mark"><v-icon :icon="BRAND.icon" size="22" /></div>
      <div>
        <div class="brand-name">{{ BRAND.name }}</div>
        <div class="brand-sub">Painel</div>
      </div>
    </div>
    <v-list nav>
      <v-list-item v-for="item in visibleNav" :key="item.title" :to="item.to" :exact="item.exact" :prepend-icon="item.icon"
                   :title="item.title">
        <template v-if="(item.ownerOnly && pendingUsers) || (item.badge === 'handoff' && waiting)" #append>
          <span class="nav-badge">{{ item.badge === 'handoff' ? waiting : pendingUsers }}</span>
        </template>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>

  <v-main>
    <header class="app-header px-4 pt-3 pb-2">
      <!-- Perfil com pop-up para foto e configurações -->
      <div v-if="admin" class="user-heading d-flex align-center min-w-0">
        <v-menu v-model="userMenuOpen" location="bottom start" :close-on-content-click="false" offset="8">
          <template #activator="{ props }">
            <button v-bind="props" class="user-heading-btn d-flex align-center ga-2 min-w-0" aria-label="Abrir menu do perfil">
              <div class="avatar-circle" aria-hidden="true">
                <img v-if="userPhoto" :src="userPhoto" alt="Foto de perfil" class="avatar-img" />
                <v-icon v-else icon="mdi-account" size="26" />
              </div>
              <div class="user-info min-w-0 text-left">
                <div class="greeting-text">Bem-vindo</div>
                <div class="user-name text-truncate">{{ adminFirstName }}</div>
              </div>
              <v-icon icon="mdi-chevron-down" size="18" class="user-chevron" />
            </button>
          </template>

          <v-card class="user-popup-card pa-4" rounded="xl" elevation="6" min-width="260" max-width="320">
            <div class="d-flex align-center ga-3 mb-3">
              <div class="avatar-preview-box">
                <img v-if="userPhoto" :src="userPhoto" alt="Foto de perfil" class="avatar-img" />
                <v-icon v-else icon="mdi-account" size="30" color="primary" />
              </div>
              <div class="min-w-0">
                <div class="font-weight-bold text-truncate user-popup-name">{{ admin?.name }}</div>
                <div class="text-caption text-medium-emphasis text-truncate">{{ admin?.email }}</div>
              </div>
            </div>

            <v-divider class="my-2" />

            <input ref="fileInput" type="file" accept="image/*" class="d-none" @change="onFilePicked" />

            <div class="d-flex flex-column ga-1 mt-2">
              <v-btn
                block
                variant="tonal"
                color="primary"
                prepend-icon="mdi-camera-outline"
                class="justify-start text-none user-popup-btn"
                size="small"
                rounded="lg"
                @click="triggerFileInput"
              >
                {{ userPhoto ? 'Trocar foto de perfil' : 'Escolher foto de perfil' }}
              </v-btn>

              <v-btn
                v-if="userPhoto"
                block
                variant="text"
                color="error"
                prepend-icon="mdi-delete-outline"
                class="justify-start text-none user-popup-btn"
                size="x-small"
                rounded="lg"
                @click="removePhoto"
              >
                Remover foto
              </v-btn>

              <v-btn
                block
                variant="text"
                prepend-icon="mdi-cog-outline"
                class="justify-start text-none user-popup-btn mt-1"
                size="small"
                rounded="lg"
                @click="goToSettings"
              >
                Configurações
              </v-btn>
            </div>
          </v-card>
        </v-menu>
      </div>

      <div class="bell-area">
        <NotificationBell />
      </div>
    </header>

    <v-container fluid class="page pa-4">
      <router-view />
    </v-container>
  </v-main>

  <!-- Navegação móvel: sem Configurações (acessada pelo pop-up de perfil) -->
  <nav v-if="!mdAndUp" class="bottom-nav" aria-label="Navegação principal">
    <router-link v-for="item in mobileNav" :key="item.title" :to="item.to" class="bottom-nav-item" exact-active-class="active"
                 :aria-label="item.title === 'Dashboard' ? 'Início' : item.title">
      <div class="icon-wrap position-relative">
        <v-icon :icon="item.title === 'Dashboard' ? 'mdi-home' : item.icon" size="20" />
        <span v-if="item.badge === 'handoff' && waiting" class="bottom-badge">{{ waiting }}</span>
        <span v-if="item.ownerOnly && pendingUsers" class="bottom-badge">{{ pendingUsers }}</span>
      </div>
      <span class="nav-label">{{ item.title === 'Dashboard' ? 'Início' : item.title }}</span>
    </router-link>
  </nav>

  <v-snackbar v-model="toast.show" :color="toast.color" :timeout="4000" location="bottom right">{{ toast.text }}</v-snackbar>
</template>

<style scoped>
.top-wave-bg {
  position: absolute;
  top: 0;
  right: 0;
  width: 100%;
  max-width: 500px;
  height: 180px;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
.wave-svg {
  width: 100%;
  height: 100%;
}

/* ========== HEADER ========== */
.app-header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 72px;
}

.min-w-0 { min-width: 0; }
.user-heading { flex: 1; }

.user-heading-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px 8px 4px 4px;
  border-radius: 28px;
  transition: background 0.15s ease;
  outline: none;
  max-width: 100%;
}
.user-heading-btn:hover {
  background: rgba(var(--v-theme-primary), 0.06);
}
.user-chevron {
  color: rgba(var(--v-theme-on-background), 0.45);
  flex-shrink: 0;
}

.avatar-circle {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  display: grid;
  place-items: center;
  box-shadow: 0 4px 12px rgba(var(--v-theme-primary), 0.25);
  flex-shrink: 0;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}

.avatar-preview-box {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.1);
  display: grid;
  place-items: center;
  overflow: hidden;
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-primary), 0.2);
}

.user-popup-card {
  background: rgb(var(--v-theme-surface)) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}

.user-popup-name {
  font-size: 0.95rem;
  color: rgb(var(--v-theme-on-surface));
}

.user-popup-btn {
  font-weight: 500;
}

.user-info {
  line-height: 1.2;
}
.greeting-text {
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-background), 0.62);
  font-weight: 500;
}
.user-name {
  font-size: 1.05rem;
  color: rgb(var(--v-theme-primary));
  font-weight: 800;
  letter-spacing: -0.01em;
}

/* Notificação: fundo semi-transparente */
.bell-area {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.08);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.bell-area :deep(.v-btn) {
  width: 100%;
  height: 100%;
  min-width: 0;
  padding: 0;
  color: rgb(var(--v-theme-primary));
}

/* ========== CONTEÚDO ========== */
.page {
  position: relative;
  z-index: 1;
}

/* ========== BARRA INFERIOR (somente mobile) ========== */
.bottom-nav {
  position: fixed;
  bottom: max(10px, env(safe-area-inset-bottom));
  left: 50%;
  transform: translateX(-50%);
  width: calc(100% - 20px);
  max-width: 720px;
  height: 70px;
  background: rgb(var(--v-theme-surface));
  border-radius: 35px;
  display: flex;
  align-items: center;
  justify-content: space-evenly;
  padding: 4px 5px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.18);
  z-index: 1000;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}

.bottom-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  color: rgba(var(--v-theme-on-surface), 0.68);
  padding: 4px 2px;
  border-radius: 20px;
  transition: all 0.2s ease;
  flex: 1 1 0;
  min-width: 0;
}

.bottom-nav-item .icon-wrap {
  width: 34px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  transition: background 0.2s, transform 0.2s;
}

.bottom-nav-item .nav-label {
  font-size: 0.58rem;
  font-weight: 600;
  margin-top: 2px;
  letter-spacing: -0.01em;
  line-height: 1.05;
  text-align: center;
  max-width: 100%;
}

.bottom-nav-item.active {
  color: rgb(var(--v-theme-primary));
}

.bottom-nav-item.active .icon-wrap {
  background: rgba(var(--v-theme-primary), 0.12);
  transform: translateY(-1px);
}

.bottom-badge {
  position: absolute;
  top: -4px;
  right: -6px;
  background: rgb(var(--v-theme-secondary));
  color: rgb(var(--v-theme-on-secondary));
  font-size: 0.62rem;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 10px;
}

/* ========== RESPONSIVIDADE ========== */

/* Mobile: perfil alinhado ao centro e sino preso ao canto superior direito. */
@media (max-width: 959px) {
  .app-header {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    max-width: 720px;
    margin: 0 auto;
    min-height: 76px;
  }
  .user-heading {
    grid-column: 1;
    justify-self: start;
    max-width: calc(100vw - 112px);
  }
  .bell-area {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
  }
  .page {
    max-width: 960px;
    margin: 0 auto;
    padding-bottom: 104px !important;
  }
  .bottom-nav-item .nav-label {
    overflow-wrap: anywhere;
  }
}

/* Desktop: conteúdo usa toda a largura disponível após a sidebar */
@media (min-width: 960px) {
  .app-header {
    max-width: 100%;
    padding: 12px 24px 8px !important;
  }
  .page {
    max-width: 100%;
    padding-bottom: 24px !important;
  }
  .top-wave-bg {
    display: none;
  }
}
</style>
