<script setup>
// Moldura das telas de acesso (login, esqueci a senha, redefinir): painel da marca + área do formulário.
</script>

<template>
  <v-main class="login">
    <aside class="hero">
      <div class="pole" aria-hidden="true" />
      <div class="hero-inner">
        <div class="brand-mark"><v-icon icon="mdi-content-cut" size="26" /></div>
        <h2>Sua agenda,<br />sem complicação.</h2>
        <p>Horários, clientes e faturamento da barbearia em um só lugar, com atendimento automático pelo WhatsApp.</p>
      </div>
    </aside>

    <section class="form-side">
      <div class="form-box">
        <div class="mobile-brand">
          <div class="brand-mark"><v-icon icon="mdi-content-cut" size="22" /></div>
          <span>Barbearia</span>
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
  background: radial-gradient(900px 500px at 15% 10%, rgba(215, 174, 98, 0.16), transparent 60%),
              radial-gradient(700px 500px at 100% 100%, rgba(127, 163, 199, 0.12), transparent 60%);
}
/* "Poste de barbeiro": faixas diagonais finas na lateral */
.pole {
  position: absolute; right: 0; top: 0; bottom: 0; width: 18px; opacity: 0.9;
  background: repeating-linear-gradient(135deg, #d7ae62 0 10px, #f3ece0 10px 20px, #2c6a8f 20px 30px, #f3ece0 30px 40px);
}
.hero-inner { position: relative; max-width: 460px; }
.hero .brand-mark { margin-bottom: 28px; }
.hero h2 { font-family: var(--font-display); font-weight: 600; font-size: 3rem; line-height: 1.08; letter-spacing: -0.02em; margin-bottom: 18px; }
.hero p { font-size: 1.05rem; line-height: 1.6; color: rgba(243, 236, 224, 0.72); }
.brand-mark { width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; background: linear-gradient(145deg, #d7ae62, #a97c2f); color: #1a1408; }

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
