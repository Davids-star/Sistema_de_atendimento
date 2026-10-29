<script setup>
import { BRAND } from '../brand'
// Moldura das telas de acesso (login, esqueci a senha, redefinir): painel da marca + área do formulário.
</script>

<template>
  <v-main class="login">
    <aside class="hero">
      <div class="pole" aria-hidden="true" />
      <div class="hero-inner">
        <div class="brand-mark"><v-icon :icon="BRAND.icon" size="26" /></div>
        <h2>Sua agenda,<br />sem complicação.</h2>
        <p>Horários, clientes e faturamento do seu negócio em um só lugar, com atendimento automático pelo WhatsApp.</p>
      </div>
    </aside>

    <section class="form-side">
      <div class="form-box">
        <div class="mobile-brand">
          <div class="brand-mark"><v-icon :icon="BRAND.icon" size="22" /></div>
          <span>{{ BRAND.name }}</span>
        </div>
        <slot />
      </div>
    </section>
  </v-main>
</template>

<style scoped>
.login { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); min-height: 100vh; }
.hero { position: relative; overflow: hidden; background: var(--ink); color: #f3ece0; display: flex; align-items: center; padding: 64px; }
.hero::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(900px 500px at 15% 10%, rgba(159, 195, 184, 0.16), transparent 60%),
              radial-gradient(700px 500px at 100% 100%, rgba(127, 163, 199, 0.12), transparent 60%);
}
/* Faixa de destaque discreta na lateral */
.pole {
  position: absolute; right: 0; top: 0; bottom: 0; width: 6px;
  background: linear-gradient(180deg, #9fc3b8, #6f9c8f 55%, #86a9c4);
}
.hero-inner { position: relative; max-width: 460px; }
.hero .brand-mark { margin-bottom: 28px; }
.hero h2 { font-family: var(--font-display); font-weight: 600; font-size: 3rem; line-height: 1.08; letter-spacing: -0.02em; margin-bottom: 18px; }
.hero p { font-size: 1.05rem; line-height: 1.6; color: rgba(243, 236, 224, 0.72); }
.brand-mark { width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; background: linear-gradient(145deg, #9fc3b8, #6f9c8f); color: #10201b; }

.form-side { display: flex; align-items: center; justify-content: center; padding: 32px; }
.form-box { width: 100%; max-width: 400px; }
.mobile-brand { display: none; align-items: center; gap: 10px; margin-bottom: 28px; font-family: var(--font-display); font-weight: 600; font-size: 1.3rem; }
.mobile-brand .brand-mark { width: 38px; height: 38px; border-radius: 11px; }

@media (max-width: 900px) {
  .login { grid-template-columns: minmax(0, 1fr); }
  .hero { display: none; }
  .mobile-brand { display: flex; }
}
</style>
